import pytest
from delek.db import get_db


def test_list(client, auth):
    response = client.get('/')
    assert b"Log In" in response.data
    assert b"Iscriviti" in response.data
    assert b"Chi Siamo" in response.data

    auth.login('user1', 'password1')
    response = client.get('/')
    assert b'Log Out' in response.data
    # TODO: add check list produttori printed

@pytest.mark.parametrize('path', (
    '/produttori/create',
    '/produttori/1/update',
    '/produttori/1/delete',
))
def test_login_required(client, path):
    response = client.post(path)
    assert response.headers['Location'] == 'http://localhost/auth/login'


def test_referente_required(app, client, auth):
    with app.app_context():
        db = get_db()
        db.execute('UPDATE produttori SET id_utente = 2 WHERE id = 1')
        db.commit()

    auth.login()

    assert client.post('/produttori/1/update').status_code == 403
    assert client.post('/produttori/1/delete').status_code == 403

    assert b'href="/produttori/1/update"' not in client.get('/produttori').data


@pytest.mark.parametrize('path', (
    '/produttori/2/update',
    '/produttori/2/delete',
))
def test_exists_required(client, auth, path):
    auth.login()
    assert client.post(path).status_code == 404

def test_create(client, auth, app):
    auth.login()
    assert client.get('/produttori/create').status_code == 200
    client.post('/produttori/create', data={'id_utente': 1, 'nome': 'rivalta'})

    with app.app_context():
        db = get_db()
        count = db.execute('SELECT COUNT(id) FROM produttori').fetchone()[0]
        assert count == 6


def test_update(client, auth, app):
    auth.login()
    assert client.get('/produttori/1/update').status_code == 200
    client.post('/produttori/1/update', data={'id_utente': 3, 'nome': 'produttore1 updated'})

    with app.app_context():
        db = get_db()
        produttori = db.execute('SELECT * FROM produttori WHERE id = 1').fetchone()
        assert 'updated' in produttori['nome']


@pytest.mark.parametrize('path', (
    '/produttori/create',
    '/produttori/1/update',
))
def test_create_update_validate(client, auth, path):
    auth.login()
    response = client.post(path, data={'id_utente': '', 'nome': 'vecchi sapori'})
    assert b'referente richiesto' in response.data

def test_delete(client, auth, app):
    auth.login()
    response = client.post('/produttori/1/delete')
    assert response.headers['Location'] == 'http://localhost/'

    with app.app_context():
        db = get_db()
        post = db.execute('SELECT * FROM post WHERE id = 1').fetchone()
        assert post is None
