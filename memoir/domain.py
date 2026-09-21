"""Pure media metadata rules, independent of storage and HTTP. Author: donglixiao."""
import datetime as dt
import math
import re

PHOTO_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp', '.gif', '.avif', '.heic', '.heif'}
VIDEO_EXTENSIONS = {'.mp4', '.mov', '.m4v', '.webm', '.mkv', '.avi'}
EDITABLE = {'title', 'description', 'date', 'precision', 'location', 'tags', 'favorite', 'coordinates'}


def validate_account(value):
    if not isinstance(value, dict):
        raise ValueError('账号资料格式错误')
    username, password, phone = value.get('username'), value.get('password'), value.get('phone', '')
    if not isinstance(username, str) or not re.fullmatch(r'[\w.-]{3,32}', username, re.UNICODE):
        raise ValueError('用户名需为 3–32 位文字、数字、下划线、点或短横线')
    validate_password(password)
    if not isinstance(phone, str) or (phone and not re.fullmatch(r'\+?[0-9 ()-]{6,24}', phone)):
        raise ValueError('手机号格式不正确，可留空')
    return username, password, phone


def validate_password(password):
    if not isinstance(password, str) or not 12 <= len(password) <= 128:
        raise ValueError('密码需为 12–128 位，至少包含字母和数字')
    if not any(c.isalpha() for c in password) or not any(c.isdigit() for c in password):
        raise ValueError('密码至少包含字母和数字')
    return password


def validate_visibility(value, users):
    if not isinstance(value, dict) or set(value) - {'scope', 'users'}:
        raise ValueError('可见范围格式错误')
    scope, selected = value.get('scope'), value.get('users', [])
    if scope not in {'all', 'admin', 'selected'} or not isinstance(selected, list):
        raise ValueError('可见范围无效')
    if len(selected) > 1000 or any(not isinstance(uid, str) or uid not in users for uid in selected):
        raise ValueError('指定用户不存在')
    if scope == 'selected' and not selected:
        raise ValueError('请至少选择一位用户')
    return {'scope': scope, 'users': list(dict.fromkeys(selected)) if scope == 'selected' else []}


def validate_security_settings(value):
    required = {'registration', 'defaultVisibility', 'sessionDays'}
    if not isinstance(value, dict) or not required <= set(value) or set(value) - required - {'defaultVideoVisibility'}:
        raise ValueError('设置格式错误')
    if type(value['registration']) is not bool or value['defaultVisibility'] not in {'admin', 'all'}:
        raise ValueError('注册或默认可见范围无效')
    if type(value['sessionDays']) is not int or not 1 <= value['sessionDays'] <= 90:
        raise ValueError('登录有效期应为 1–90 天；调整后新登录生效')
    if 'defaultVideoVisibility' in value and value['defaultVideoVisibility'] not in {'admin', 'all'}:
        raise ValueError('视频默认可见范围无效')
    return dict(value)


def default_visibility(settings, kind=None):
    """Old installations retain their existing default until explicitly changed."""
    if kind == 'video':
        return settings.get('defaultVideoVisibility', settings['defaultVisibility'])
    return settings['defaultVisibility']


def validate_coordinates(value):
    """WGS84 degrees; null explicitly removes an original GPS position."""
    if value is None:
        return None
    if not isinstance(value, dict) or set(value) != {'latitude', 'longitude'}:
        raise ValueError('请同时填写纬度和经度')
    for key, limit in [('latitude', 90), ('longitude', 180)]:
        number = value[key]
        if isinstance(number, bool) or not isinstance(number, (int, float)) or not math.isfinite(number) or abs(number) > limit:
            raise ValueError('纬度应在 -90 至 90，经度应在 -180 至 180 之间')
    return dict(value)


def inferred_date(filename):
    """Only infer explicit calendar dates; file modification is not a capture date."""
    match = re.search(r'(20\d{2})[-_]?([01]\d)[-_]?([0-3]\d)', filename)
    if match:
        try:
            return dt.date(*map(int, match.groups())).isoformat()
        except ValueError:
            pass
    return ''


def validate_edit(value):
    if not isinstance(value, dict) or set(value) - EDITABLE:
        raise ValueError('包含不支持的回忆字段')
    result = {}
    if 'coordinates' in value:
        result['coordinates'] = validate_coordinates(value['coordinates'])
    for key, limit in [('title', 120), ('description', 3000), ('location', 100)]:
        if key in value:
            if not isinstance(value[key], str) or len(value[key]) > limit:
                raise ValueError(f'{key} 格式错误或内容过长')
            result[key] = value[key].strip()
    if 'favorite' in value:
        if not isinstance(value['favorite'], bool):
            raise ValueError('珍藏状态格式错误')
        result['favorite'] = value['favorite']
    if 'tags' in value:
        tags = value['tags']
        if not isinstance(tags, list) or len(tags) > 20 or any(not isinstance(t, str) or len(t) > 30 for t in tags):
            raise ValueError('最多 20 个标签，每个标签最多 30 字')
        result['tags'] = list(dict.fromkeys(t.strip().lstrip('#') for t in tags if t.strip().lstrip('#')))
    if 'date' in value or 'precision' in value:
        date, precision = value.get('date', ''), value.get('precision', 'unknown')
        if not isinstance(date, str) or precision not in {'day', 'month', 'unknown'}:
            raise ValueError('拍摄日期格式错误')
        if precision == 'unknown':
            date = ''
        else:
            pattern = r'\d{4}-\d{2}' if precision == 'month' else r'\d{4}-\d{2}-\d{2}'
            if not re.fullmatch(pattern, date):
                raise ValueError('请填写完整的拍摄日期')
            try:
                dt.date.fromisoformat(date + '-01' if precision == 'month' else date)
            except ValueError as exc:
                raise ValueError('拍摄日期不存在') from exc
        result.update(date=date, precision=precision)
    return result


def validate_batch(value):
    if not isinstance(value, dict) or set(value) - {'ids', 'changes', 'tagMode'}:
        raise ValueError('批量请求格式错误')
    ids = value.get('ids')
    if not isinstance(ids, list) or not 1 <= len(ids) <= 200 or any(
        not isinstance(identity, str) or not re.fullmatch(r'[a-f0-9]{20}', identity)
        for identity in ids
    ):
        raise ValueError('每次请选择 1 至 200 条回忆')
    changes = validate_edit(value.get('changes'))
    if not changes or set(changes) - {'date', 'precision', 'location', 'tags', 'favorite'}:
        raise ValueError('批量整理仅支持日期、地点、标签和珍藏')
    tag_mode = value.get('tagMode', 'append')
    if tag_mode not in {'append', 'replace', 'remove'}:
        raise ValueError('标签操作不正确')
    return list(dict.fromkeys(ids)), changes, tag_mode
