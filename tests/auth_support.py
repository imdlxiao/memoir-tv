"""Explicit test-owner setup in temporary repositories only. Author: donglixiao."""
PASSWORD = 'Fixture-Password-2026'


def owner_session(app):
    owner, session = app.auth.create({'username': 'test-owner', 'password': PASSWORD,
                                     'code': app.auth.store.setup_code()}, setup=True)
    app.auth.settings(owner, {'registration': True, 'defaultVisibility': 'all', 'sessionDays': 30})
    return 'memoir_session=' + session[0]


def browser_owner(page, server, repository):
    base = f'http://127.0.0.1:{server.server_port}'
    code = (repository.directory / 'security' / 'setup-code.txt').read_text(encoding='utf-8')
    response = page.request.post(base + '/api/auth/setup', data={
        'username': 'test-owner', 'password': PASSWORD, 'code': code})
    assert response.status == 200, response.text()
    response = page.request.patch(base + '/api/admin/settings', data={
        'registration': True, 'defaultVisibility': 'all', 'sessionDays': 30})
    assert response.status == 200, response.text()
    catalog = page.request.get(base + '/api/catalog').json()
    for item in catalog['items']:
        response = page.request.patch(base + '/api/admin/visibility/' + item['id'], data={'scope': 'all', 'users': []})
        assert response.status == 200
