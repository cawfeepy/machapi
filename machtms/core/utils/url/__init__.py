from urllib.parse import urlparse, urlunparse, parse_qs, urlencode, urljoin


def get_encoded_params(parsed_url, **new_params) -> str:
    params: dict = parse_qs(parsed_url.query)

    for key, value in new_params.items():
        if isinstance(value, list):
            params[key] = value
        else:
            params[key] = [value]

    encoded_params = urlencode(params, doseq=True)
    return encoded_params


def construct_url_from_cache_key(
        url,
        new_path,
        cached_api_url,
        organization_id=None,
        **kwargs
    ):
    if organization_id is not None and organization_id != "_":
        kwargs.update({"organization_id": organization_id})
    base_url = urljoin(url, new_path)

    parsed_url = urlparse(base_url)
    parsed_api_url = urlparse(cached_api_url)

    encoded_params: str = get_encoded_params(parsed_api_url, **kwargs)

    new_url = urlunparse(parsed_url._replace(query=encoded_params))
    return new_url
