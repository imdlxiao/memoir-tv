"""Pure media metadata rules, independent of storage and HTTP. Author: donglixiao."""
import datetime as dt
import re

PHOTO_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp', '.gif', '.avif', '.heic', '.heif'}
VIDEO_EXTENSIONS = {'.mp4', '.mov', '.m4v', '.webm', '.mkv', '.avi'}
EDITABLE = {'title', 'description', 'date', 'precision', 'location', 'tags', 'favorite'}


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
