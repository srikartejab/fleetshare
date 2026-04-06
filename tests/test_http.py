from fleetshare_common.http import _extract_error_detail


class _FakeResponse:
    def __init__(self, text: str, reason_phrase: str = "Unprocessable Content"):
        self.text = text
        self.reason_phrase = reason_phrase


def test_extract_error_detail_flattens_nested_fastapi_validation_error():
    response = _FakeResponse(
        '{"detail":"{\\"detail\\":[{\\"type\\":\\"int_parsing\\",\\"msg\\":\\"Input should be a valid integer\\"}]}"}'
    )

    assert _extract_error_detail(response) == "Input should be a valid integer"


def test_extract_error_detail_falls_back_to_reason_phrase():
    response = _FakeResponse("", reason_phrase="Bad Gateway")

    assert _extract_error_detail(response) == "Bad Gateway"
