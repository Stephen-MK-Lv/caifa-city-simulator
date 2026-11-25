import os
from test_api import client


def auth(client, username, password):
    response = client.post('/api/auth/login', json={'username': username, 'password': password})
    assert response.status_code == 200, response.text
    return {'Authorization': 'Bearer ' + response.json()['access_token']}


def test_classroom_assignment_grading_and_private_city(client, monkeypatch):
    monkeypatch.setenv('CAIFA_AUTH_REQUIRED', '1')
    assert client.get('/api/auth/status').json()['setup_required'] is True
    teacher_setup = client.post('/api/auth/bootstrap', json={
        'username': 'teacher1', 'password': 'Teacher#2026!', 'display_name': '任课教师'})
    assert teacher_setup.status_code == 201, teacher_setup.text
    teacher = auth(client, 'teacher1', 'Teacher#2026!')

    class_row = client.post('/api/teaching/classes', headers=teacher,
                            json={'name': '政府会计学测试班', 'term': '2026秋'})
    assert class_row.status_code == 201, class_row.text
    class_id = class_row.json()['id']
    for username, name in [('student01', '学生甲'), ('student02', '学生乙')]:
        response = client.post(f'/api/teaching/classes/{class_id}/students', headers=teacher, json={
            'username': username, 'password': 'Student#2026!', 'display_name': name})
        assert response.status_code == 201, response.text

    assignment = client.post('/api/teaching/assignments', headers=teacher, json={
        'class_id': class_id, 'chapter': 3, 'title': '医院设备购置实训',
        'instruction': '独立编制分录并核对资产确认依据。', 'kind': 'purchase',
        'entity': 'hospital', 'amount': 5000, 'amount_variation_percent': 0,
        'asset_name': '教学设备', 'life': 60})
    assert assignment.status_code == 201, assignment.text
    task_id = assignment.json()['id']
    works = client.get(f'/api/teaching/assignments/{task_id}/works', headers=teacher).json()['works']
    assert len(works) == 2
    assert works[0]['case']['event_id'] != works[1]['case']['event_id']
    assert 'reference_entries' not in works[0]

    students = [auth(client, 'student01', 'Student#2026!'), auth(client, 'student02', 'Student#2026!')]
    student_works = [client.get('/api/teaching/dashboard', headers=h).json()['works'][0] for h in students]
    sim_a = student_works[0]['simulation']['simulation']['id']
    sim_b = student_works[1]['simulation']['simulation']['id']
    assert sim_a != sim_b
    assert client.get(f'/api/simulations/{sim_b}', headers=students[0]).status_code == 404

    before = student_works[0]['simulation']['voucher_count']
    submitted = client.post(f"/api/teaching/works/{student_works[0]['id']}/submit", headers=students[0], json={
        'entries': [{'entity': 'hospital', 'book': 'financial', 'side': 'debit',
                     'account': '固定资产', 'amount_yuan': 1}],
        'student_note': '逐项核对账户和金额。'})
    assert submitted.status_code == 200, submitted.text
    assessment = submitted.json()['assessment']
    assert assessment['provisional'] is True
    assert assessment['basis'] and assessment['line_feedback']
    dashboard = client.get('/api/teaching/dashboard', headers=students[0]).json()
    work = dashboard['works'][0]
    assert work['simulation']['voucher_count'] == before

    dispute = client.post(f"/api/teaching/works/{work['id']}/check", headers=students[0], json={
        'action': 'dispute', 'note': '我认为参考口径需教师复核。'})
    assert dispute.status_code == 200, dispute.text
    confirm = client.post(f"/api/teaching/works/{work['id']}/check", headers=students[0], json={
        'action': 'confirm', 'note': '已核查系统提示，确认写入本人的教学账套。'})
    assert confirm.status_code == 200, confirm.text
    after = client.get('/api/teaching/dashboard', headers=students[0]).json()['works'][0]
    assert after['confirmed'] is True
    assert after['simulation']['voucher_count'] > before

    review = client.post(f"/api/teaching/works/{work['id']}/teacher-review", headers=teacher, json={
        'score': 82, 'decision': 'confirmed', 'rationale': '已结合业务实质和制度依据复核。'})
    assert review.status_code == 200, review.text
    overview = client.get('/api/teaching/overview', headers=students[0]).json()
    assert overview['summary']['city_accounts'] == 1
    assert all(item['simulation']['owner_user_id'] if 'owner_user_id' in item['simulation'] else True
               for item in overview['city_simulations'])
