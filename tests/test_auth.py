import pytest
from flask import g, session
from delek.db import get_db

registrazione_ok = b'Registrazione avvenuta'

def test_register(client, app):
    assert client.get('/auth/register').status_code == 200
    response = client.post(
        '/auth/register', data={'username': 'utenteTest', 'password': 'pwdTest', 'email': 'email@test.com' }
    )
    assert registrazione_ok in response.data

    with app.app_context():
        assert get_db().execute(
            "select * from utenti where username = 'utenteTest'",
        ).fetchone() is not None


@pytest.mark.parametrize(('username', 'password', 'email', 'message'), (
    ('', '', '', b'Username richiesto'),
    ('a', '', '', b'Password richiesta'),
    ('a', 'b', '', b'Email richiesta'),
    ('test', 'testPassword', 'email@test.com', registrazione_ok),
))
def test_register_validate_input(client, username, password, email, message):
    response = client.post(
            '/auth/register',
            data={'username': username, 'password': password, 'email': email}
            )
    assert message in response.data

def test_login(client, auth):
    assert client.get('/auth/login').status_code == 200
    response = auth.login('user1', 'password1') # see tests/data.sql
    assert b'redirected' in response.data

    with client:
        client.get('/auth/login')
        assert session['id_utente'] == 1
        assert g.user['username'] == 'user1'


@pytest.mark.parametrize(('username', 'password', 'message'), (
    ('a', 'test', b'Username o password errati'),
))
def test_login_validate_input(auth, username, password, message):
    response = auth.login(username, password)
    assert message in response.data

def test_logout(client, auth):
    auth.login()

    with client:
        auth.logout()
        assert 'id_utente' not in session
