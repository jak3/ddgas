""" Verifica statica (nessun DB/app necessari) che ogni <form method="post">
nei template contenga {{ csrf_field() }}, cosi un futuro form aggiunto o
modificato senza il campo non passa inosservato. """
import os
import re

TEMPLATES_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'delek', 'templates')

FORM_POST_RE = re.compile(r'<form\b[^>]*method=["\']post["\']', re.IGNORECASE)
CSRF_FIELD_RE = re.compile(r'csrf_field\(\)')


def _template_files():
    for root, _dirs, files in os.walk(TEMPLATES_DIR):
        for fname in files:
            if fname.endswith('.html'):
                yield os.path.join(root, fname)


def test_ogni_form_post_ha_csrf_field():
    mancanti = []
    for path in _template_files():
        with open(path, encoding='utf8') as f:
            content = f.read()
        n_form = len(FORM_POST_RE.findall(content))
        n_csrf = len(CSRF_FIELD_RE.findall(content))
        if n_form > n_csrf:
            mancanti.append((os.path.relpath(path, TEMPLATES_DIR),
                             n_form, n_csrf))

    assert not mancanti, (
        'Template con <form method="post"> senza csrf_field() a sufficienza'
        ' (file, n_form, n_csrf_field): {0}'.format(mancanti))
