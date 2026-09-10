from app.services.config import Settings


def test_gemini_model_default_is_2_5_flash():
    assert Settings().GEMINI_MODEL == "gemini-2.5-flash"


def test_cors_origins_list_single():
    s = Settings(CORS_ORIGINS="http://localhost:5173")
    assert s.cors_origins_list == ["http://localhost:5173"]


def test_cors_origins_list_multiple():
    s = Settings(CORS_ORIGINS="http://localhost:5173, https://smart-sdlc.example.com")
    assert s.cors_origins_list == [
        "http://localhost:5173",
        "https://smart-sdlc.example.com",
    ]


def test_cors_origins_list_strips_whitespace():
    s = Settings(CORS_ORIGINS="  http://a.com , http://b.com  ")
    assert s.cors_origins_list == ["http://a.com", "http://b.com"]


def test_cors_origins_list_empty():
    assert Settings(CORS_ORIGINS="").cors_origins_list == []