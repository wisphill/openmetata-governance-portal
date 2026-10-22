from app.auth.session import SessionStore


def test_signed_cookie_resolves_its_session():
    store = SessionStore("a" * 32)
    session = store.create_pending()

    assert store.get(store.signed_id(session.id)) == session


def test_tampered_cookie_is_rejected():
    store = SessionStore("a" * 32)
    session = store.create_pending()

    assert store.get(f"{store.signed_id(session.id)}changed") is None
