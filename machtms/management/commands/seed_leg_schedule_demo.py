"""
Seed three demo loads and render the /api/loads/leg-schedule/ output for them.

This command creates the exact scenario the team wanted to eyeball:

    1. Load A - two legs, BOTH assigned
    2. Load B - two legs, FIRST assigned, second UNASSIGNED
    3. Load C - two legs, BOTH unassigned

It then runs the *real* leg-schedule pipeline (the same helpers the
``LoadViewSet.leg_schedule`` action uses -- ``order_legs``, ``leg_in_windows``,
``leg_earliest_start`` and ``LegRowSerializer``) against a single date window and
prints each emitted leg in a pretty box, so what you see here is byte-for-byte
what the endpoint returns (one flat chronological stream, one box per in-window
leg, with previous_legs / next_legs context).

Because the dev/test stack runs on disposable testcontainers, this command is
idempotent: it deletes any previously-seeded demo loads (matched by their
``trip_id`` prefix) before recreating them, so you can run it repeatedly.

Usage (DEBUG seeds need the testcontainer DB + DEBUG manager short-circuit):

    # With a live testcontainer dev DB already up (e.g. via `manage.py devserver`)
    DJANGO_SETTINGS_MODULE=api.settings uv run python manage.py seed_leg_schedule_demo

    # Or fully self-contained: spin up throwaway containers just for this run
    DJANGO_SETTINGS_MODULE=api.settings uv run python manage.py seed_leg_schedule_demo --with-containers

    # Render only, against whatever is already in the DB (no create/delete):
    ... seed_leg_schedule_demo --render-only

Options:
    --date YYYY-MM-DD   Local day to seed/query (default: 2025-06-01)
    --timezone NAME     IANA timezone for the day window (default: America/Los_Angeles)
    --with-containers   Boot Postgres/RabbitMQ/Redis testcontainers for this run
    --render-only       Skip seeding; just render existing demo loads
    --keep              Do not delete previously-seeded demo loads first
    --no-color          Disable ANSI colors in the boxes
"""
from __future__ import annotations

import os
from datetime import datetime, time
from zoneinfo import ZoneInfo

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

# A stable marker so re-runs can find and replace prior demo data.
DEMO_TRIP_PREFIX = "DEMO-LEGSCHED"

# Box drawing + a small palette. Kept local so the command has no extra deps.
_BOX = {
    "tl": "╭", "tr": "╮", "bl": "╰", "br": "╯",
    "h": "─", "v": "│",
}

# Sentinel: a line equal to this is expanded to a full-width divider by _box().
_RULE = "\x00RULE\x00"


class _Palette:
    """ANSI helpers; all no-ops when color is disabled."""

    def __init__(self, enabled: bool):
        self.enabled = enabled

    def _wrap(self, code: str, text: str) -> str:
        return f"\033[{code}m{text}\033[0m" if self.enabled else text

    def bold(self, t: str) -> str:
        return self._wrap("1", t)

    def dim(self, t: str) -> str:
        return self._wrap("2", t)

    def green(self, t: str) -> str:
        return self._wrap("32", t)

    def yellow(self, t: str) -> str:
        return self._wrap("33", t)

    def cyan(self, t: str) -> str:
        return self._wrap("36", t)

    def red(self, t: str) -> str:
        return self._wrap("31", t)


class Command(BaseCommand):
    help = (
        "Seed three demo loads (both-assigned / mixed / both-unassigned) and "
        "pretty-print the leg-schedule output, one box per leg."
    )

    def add_arguments(self, parser):
        parser.add_argument("--date", default="2025-06-01")
        parser.add_argument("--timezone", default="America/Los_Angeles")
        parser.add_argument("--with-containers", action="store_true")
        parser.add_argument("--render-only", action="store_true")
        parser.add_argument("--keep", action="store_true")
        parser.add_argument(
            "--plain", action="store_true",
            help="Disable ANSI colors in the boxes (also honors Django's --no-color).",
        )
        # NOTE: Django's BaseCommand already provides --no-color and --force-color
        # on every command, so we read those from options instead of redefining
        # them (redefining raises an argparse conflict).

    # ------------------------------------------------------------------ #
    # entrypoint
    # ------------------------------------------------------------------ #
    def handle(self, *args, **options):
        # Honor our own --plain, Django's global --no-color, and non-tty output.
        # Django's --force-color overrides the tty check (e.g. piping to `less -R`).
        color_off = options["plain"] or options.get("no_color")
        if not options.get("force_color"):
            color_off = color_off or not os.isatty(1)
        self.p = _Palette(enabled=not color_off)

        # Stop.save() dispatches an address-usage Celery task. For a seeding
        # script we don't want (or need) a live broker/worker, so force eager
        # execution: the task runs inline and never touches RabbitMQ.
        self._force_celery_eager()

        try:
            tz = ZoneInfo(options["timezone"])
        except Exception as exc:  # noqa: BLE001 - surface a clean CommandError
            raise CommandError(f"Invalid IANA timezone: {options['timezone']}") from exc

        try:
            day = datetime.strptime(options["date"], "%Y-%m-%d").date()
        except ValueError as exc:
            raise CommandError(f"Invalid --date (expected YYYY-MM-DD): {options['date']}") from exc

        if not settings.DEBUG:
            self.stdout.write(self.p.yellow(
                "WARNING: settings.DEBUG is False. The TMS `fbo()` manager will "
                "filter by organization, so the render step may show nothing "
                "unless the demo loads share the active org. Run with DEBUG=True."
            ))

        if options["with_containers"]:
            with self._containers():
                self._run(day, tz, options)
        else:
            self._run(day, tz, options)

    def _run(self, day, tz, options):
        if not options["render_only"]:
            if not options["keep"]:
                self._purge_previous()
            loads = self._seed(day, tz)
            self.stdout.write(self.p.green(
                f"Seeded {len(loads)} demo loads for {day} ({tz}).\n"
            ))

        self._render(day, tz)

    def _force_celery_eager(self):
        """Run Celery tasks inline (no broker) for the duration of this command."""
        try:
            from api.celery import app as celery_app
            celery_app.conf.task_always_eager = True
            celery_app.conf.task_eager_propagates = False
            celery_app.conf.task_store_eager_result = False
        except Exception as exc:  # noqa: BLE001 - eager is best-effort convenience
            self.stdout.write(self.p.dim(f"(could not force Celery eager: {exc})"))

    # ------------------------------------------------------------------ #
    # testcontainers (optional, mirrors the devserver command)
    # ------------------------------------------------------------------ #
    def _containers(self):
        from contextlib import contextmanager

        @contextmanager
        def _ctx():
            from api.mach_testcontainers import (
                PostgresTestContainer,
                RabbitMQTestContainer,
                RedisTestContainer,
            )
            from django.core.management import call_command
            from django.db import connections

            pg = PostgresTestContainer()
            rabbit = RabbitMQTestContainer()
            redis = RedisTestContainer()
            original_databases = dict(settings.DATABASES)
            self.stdout.write(self.p.dim("Starting testcontainers (pg/rabbit/redis)..."))
            pg.start()
            rabbit.start()
            redis.start()
            try:
                # Point Django's default connection at the throwaway Postgres,
                # exactly the way the devserver command rewires it.
                settings.DATABASES["default"] = pg.get_django_db_settings()
                connections.close_all()
                if hasattr(connections._connections, "default"):
                    del connections._connections.default
                connections._settings = connections.configure_settings(settings.DATABASES)
                call_command("migrate", interactive=False, verbosity=0)
                yield
            finally:
                self.stdout.write(self.p.dim("Stopping testcontainers..."))
                connections.close_all()
                settings.DATABASES = original_databases
                for c in (redis, rabbit, pg):
                    try:
                        c.stop()
                    except Exception:  # noqa: BLE001 - best-effort teardown
                        pass

        return _ctx()

    # ------------------------------------------------------------------ #
    # seeding with factory_boy
    # ------------------------------------------------------------------ #
    def _purge_previous(self):
        from machtms.backend.loads.models import Load

        qs = Load.objects.filter(trip_id__startswith=DEMO_TRIP_PREFIX)
        count = qs.count()
        if count:
            qs.delete()  # cascades to legs -> stops + shipment_assignment
            self.stdout.write(self.p.dim(f"Removed {count} previously-seeded demo load(s)."))

    @transaction.atomic
    def _seed(self, day, tz):
        """
        Build the three loads with factory_boy and return them.

        We reuse the project's factories (LoadFactory, LegFactory, StopFactory,
        ShipmentAssignmentFactory, AddressFactory, CarrierFactory, DriverFactory)
        and only override the few fields we care about for a readable demo
        (reference_number, trip_id, status, stop times/addresses, owner).
        """
        from machtms.core.factories.loads import LoadFactory
        from machtms.core.factories.leg import LegFactory, ShipmentAssignmentFactory
        from machtms.core.factories.routes import StopFactory
        from machtms.core.factories.addresses import AddressFactory
        from machtms.core.factories.carrier import CarrierFactory, DriverFactory
        from machtms.core.factories.customer import CustomerFactory
        from machtms.backend.loads.models import LoadStatus

        def at(hour, minute=0):
            """A tz-aware datetime on the chosen local day."""
            return datetime.combine(day, time(hour, minute), tzinfo=tz)

        # Shared customer + a couple of carriers/drivers so the boxes read nicely.
        customer = CustomerFactory.create(customer_name="Acme Logistics")
        speedy = CarrierFactory.create(carrier_name="Speedy Freight")
        john = DriverFactory.create(carrier=speedy, first_name="John", last_name="Doe")
        crosscountry = CarrierFactory.create(carrier_name="Cross Country Hauling")
        maria = DriverFactory.create(carrier=crosscountry, first_name="Maria", last_name="Lopez")

        def make_leg(load, pickup_hour, pu_place, pu_city, pu_state,
                     deliver_hour, do_place, do_city, do_state,
                     assigned_to=None):
            """One pickup + one delivery stop; optionally assign a carrier/driver."""
            leg = LegFactory.create(load=load)
            StopFactory.create(
                leg=leg, stop_number=1, action="LL",
                address=AddressFactory.create(place_name=pu_place, city=pu_city, state=pu_state),
                start_range=at(pickup_hour), end_range=at(pickup_hour + 2),
                po_numbers="PO-1001", driver_notes="Dock 4. Call on arrival.",
            )
            StopFactory.create(
                leg=leg, stop_number=2, action="LU",
                address=AddressFactory.create(place_name=do_place, city=do_city, state=do_state),
                start_range=at(deliver_hour), end_range=at(deliver_hour + 2),
                po_numbers="PO-1001", driver_notes="Lumper paid.",
            )
            if assigned_to is not None:
                carrier, driver = assigned_to
                ShipmentAssignmentFactory.create(leg=leg, carrier=carrier, driver=driver)
            return leg

        loads = []

        # 1) Load A - two legs, BOTH assigned.
        load_a = LoadFactory.create(
            reference_number="REF-A1", trip_id=f"{DEMO_TRIP_PREFIX}-A",
            customer=customer, status=LoadStatus.ASSIGNED,
        )
        make_leg(load_a, 6, "Walmart DC", "Dallas", "TX",
                 10, "Target DC", "Phoenix", "AZ", assigned_to=(speedy, john))
        make_leg(load_a, 12, "Target DC", "Phoenix", "AZ",
                 17, "Costco DC", "Denver", "CO", assigned_to=(crosscountry, maria))
        loads.append(load_a)

        # 2) Load B - two legs, FIRST assigned, second UNASSIGNED.
        load_b = LoadFactory.create(
            reference_number="REF-B2", trip_id=f"{DEMO_TRIP_PREFIX}-B",
            customer=customer, status=LoadStatus.PENDING,
        )
        make_leg(load_b, 8, "Home Depot DC", "Houston", "TX",
                 13, "Lowe's DC", "Austin", "TX", assigned_to=(speedy, john))
        make_leg(load_b, 15, "Lowe's DC", "Austin", "TX",
                 20, "Menards DC", "San Antonio", "TX", assigned_to=None)
        loads.append(load_b)

        # 3) Load C - two legs, BOTH unassigned.
        load_c = LoadFactory.create(
            reference_number="REF-C3", trip_id=f"{DEMO_TRIP_PREFIX}-C",
            customer=customer, status=LoadStatus.PENDING,
        )
        make_leg(load_c, 9, "Kroger DC", "Atlanta", "GA",
                 14, "Publix DC", "Orlando", "FL", assigned_to=None)
        make_leg(load_c, 16, "Publix DC", "Orlando", "FL",
                 21, "Winn-Dixie DC", "Tampa", "FL", assigned_to=None)
        loads.append(load_c)

        return loads

    # ------------------------------------------------------------------ #
    # render: run the REAL leg-schedule pipeline and box every emitted leg
    # ------------------------------------------------------------------ #
    def _render(self, day, tz):
        from django.db.models import Prefetch, Q

        from machtms.backend.loads.models import Load
        from machtms.backend.legs.models import Leg, ShipmentAssignment
        from machtms.backend.routes.models import Stop
        from machtms.backend.loads.serializers import (
            order_legs, leg_in_windows, leg_earliest_start, LegRowSerializer,
        )

        # Build the same UTC day-window the LegScheduleQuerySerializer would.
        utc = ZoneInfo("UTC")
        local_start = datetime.combine(day, time.min, tzinfo=tz)
        local_end = datetime.combine(day, time(23, 59, 59, 999999), tzinfo=tz)
        windows = [(local_start.astimezone(utc), local_end.astimezone(utc))]

        # Mirror the view's queryset (fbo() -> all() under DEBUG) + prefetches.
        window_q = Q()
        for start, end in windows:
            window_q |= Q(legs__stops__start_range__range=(start, end))

        queryset = (
            Load.objects.fbo()
            .filter(window_q)
            .distinct()
            .select_related("customer")
            .prefetch_related(
                Prefetch(
                    "legs",
                    queryset=Leg.objects.prefetch_related(
                        Prefetch(
                            "stops",
                            queryset=Stop.objects.select_related("address").order_by("stop_number"),
                        ),
                        Prefetch(
                            "shipment_assignment",
                            queryset=ShipmentAssignment.objects.select_related("carrier", "driver"),
                        ),
                    ).order_by("pk"),
                ),
            )
        )

        # Exactly the view's flatten + sort.
        rows = []
        for load in queryset:
            ordered = order_legs(load)
            for index, leg in enumerate(ordered):
                leg._ordered_siblings = ordered
                leg._seq_index = index
                if leg_in_windows(leg, windows):
                    leg._row_sort_key = leg_earliest_start(leg)
                    rows.append(leg)
        rows.sort(key=lambda leg: (leg._row_sort_key, leg.pk))

        data = LegRowSerializer(rows, many=True).data

        self._print_header(day, tz, count=len(data))
        if not data:
            self.stdout.write(self.p.red(
                "No in-window legs found. Did seeding run? Is DEBUG=True so the "
                "org filter is bypassed? Try --date / --timezone matching the seed."
            ))
            return

        for row in data:
            self._print_leg_box(row)
        self.stdout.write("")
        self.stdout.write(self.p.dim(
            "Note: results are ONE flat chronological stream (earliest pickup "
            "first). A load's legs may be split apart by other loads' legs. "
            "previous_legs / next_legs carry full-trip context even for legs "
            "that fall outside the window."
        ))

    # ------------------------------------------------------------------ #
    # pretty-printing helpers
    # ------------------------------------------------------------------ #
    def _print_header(self, day, tz, count):
        self.stdout.write("")
        self.stdout.write(self.p.bold(
            f"LEG SCHEDULE  -  {day}  ({tz})  -  {count} leg row(s)"
        ))
        self.stdout.write(self.p.dim("=" * 64))
        self.stdout.write("")

    def _fmt_dt(self, value):
        """ISO -> 'Jun 01 06:00Z' for compact boxes; passthrough on None."""
        if not value:
            return "--"
        try:
            # DRF serializes to ISO strings; parse back for tidy display.
            dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            return dt.strftime("%b %d %H:%M") + "Z"
        except ValueError:
            return str(value)

    # Hard ceiling so a very long line is truncated instead of blowing out the
    # box. Wide enough to fit a fully-named sibling row on one line.
    _MAX_BOX_WIDTH = 96

    def _box(self, lines):
        """Render lines inside a box auto-sized to the widest (visible) line."""
        # Truncate any non-rule line wider than the ceiling so borders align.
        content_cap = self._MAX_BOX_WIDTH - 4
        norm = [ln if ln == _RULE else self._truncate(ln, content_cap) for ln in lines]
        # Inner width is driven by real content, never by the rule sentinel.
        inner = max((self._visible_len(ln) for ln in norm if ln != _RULE), default=0)
        width = inner + 4  # 2 borders + 2 padding spaces

        top = _BOX["tl"] + _BOX["h"] * (width - 2) + _BOX["tr"]
        bottom = _BOX["bl"] + _BOX["h"] * (width - 2) + _BOX["br"]
        out = [top]
        for ln in norm:
            if ln == _RULE:
                out.append(f"{_BOX['v']}{self.p.dim(_BOX['h'] * (width - 2))}{_BOX['v']}")
                continue
            pad = max(0, inner - self._visible_len(ln))
            out.append(f"{_BOX['v']} {ln}{' ' * pad} {_BOX['v']}")
        out.append(bottom)
        return out

    def _truncate(self, text, cap):
        """Truncate to `cap` visible chars (preserving ANSI), adding an ellipsis."""
        if self._visible_len(text) <= cap:
            return text
        import re
        # Walk the string, copying chars but skipping ANSI runs from the budget.
        # Reserve one visible column for the ellipsis.
        out, visible, i = [], 0, 0
        ansi = re.compile(r"\033\[[0-9;]*m")
        while i < len(text) and visible < cap - 1:
            m = ansi.match(text, i)
            if m:
                out.append(m.group())
                i = m.end()
                continue
            out.append(text[i])
            visible += 1
            i += 1
        # Close any open color run only when colors are actually enabled.
        reset = "\033[0m" if self.p.enabled else ""
        return "".join(out) + "…" + reset

    @staticmethod
    def _visible_len(text):
        """Length of a string ignoring ANSI escape sequences."""
        import re
        return len(re.sub(r"\033\[[0-9;]*m", "", text))

    def _owner_str_from_row(self, row):
        owner = row["owner"]
        if owner is None:
            return self.p.yellow("UNASSIGNED")
        carrier = owner["carrier"]["carrier_name"]
        driver = owner["driver"]["full_name"]
        return self.p.green(f"{carrier} / {driver}")

    def _print_leg_box(self, row):
        ref = row["reference_number"]
        seq = row["sequence_index"]
        leg_label = self.p.bold(f"Leg {seq + 1}") + self.p.dim(f"  (sequence_index={seq})")
        assigned = row["is_assigned"]
        badge = self.p.green("ASSIGNED") if assigned else self.p.yellow("UNASSIGNED")

        lines = []
        lines.append(self.p.cyan(self.p.bold(f"Load {ref}")) + self.p.dim(f"   leg_id={row['leg_id']}"))
        lines.append(f"{leg_label}   [{badge}]")
        lines.append(self.p.dim(f"status={row['status']}  trip_id={row['trip_id']}  bol={row['bol_number']}"))
        cust = row["customer"]["customer_name"] if row["customer"] else "--"
        lines.append(self.p.dim(f"customer: {cust}"))
        lines.append(f"owner: {self._owner_str_from_row(row)}")
        lines.append(_RULE)  # full-width divider, expanded by _box()

        # This leg's own stops (full detail).
        lines.append(self.p.bold("stops:"))
        for stop in row["stops"]:
            addr = stop.get("address") or {}
            place = addr.get("place_name", "?")
            city = addr.get("city", "?")
            state = addr.get("state", "?")
            window = f"{self._fmt_dt(stop.get('start_range'))} -> {self._fmt_dt(stop.get('end_range'))}"
            lines.append(
                f"  [{stop.get('action_display', stop.get('action', '?'))}] "
                f"{place} - {city}, {state}"
            )
            lines.append(self.p.dim(f"      {window}"))

        # Sibling context.
        self._append_siblings(lines, "previous_legs", row["previous_legs"])
        self._append_siblings(lines, "next_legs", row["next_legs"])

        for line in self._box(lines):
            self.stdout.write(line)
        self.stdout.write("")

    def _append_siblings(self, lines, label, siblings):
        if not siblings:
            lines.append(self.p.dim(f"{label}: (none)"))
            return
        lines.append(self.p.dim(f"{label}:"))
        for sib in siblings:
            first = sib["stops"][0] if sib["stops"] else {}
            where = first.get("label") or "no stops"
            when = self._fmt_dt(first.get("start_range")) if first else "--"
            owner = sib["owner"]
            owner_disp = self.p.green(owner) if owner != "unassigned" else self.p.yellow(owner)
            seq = sib["sequence_index"] + 1
            lines.append(
                self.p.dim(f"   - leg #{seq} (") + owner_disp + self.p.dim(f")  {where} @ {when}")
            )
