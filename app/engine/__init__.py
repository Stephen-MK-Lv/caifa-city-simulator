from .legacy_city import City, NAMES, fen

# Keep the historical engine file unchanged; rebrand its shared entity labels.
# Entity keys, accounting rules, checkpoints and random sequences are unchanged.
NAMES.update({
    'fiscal': '彩珐市财政局总会计',
    'hospital': '彩珐市人民医院',
    'school': '彩珐市职业学校',
    'police': '彩珐市公安局',
    'soe': '彩珐市城市实业有限公司',
})

__all__ = ['City', 'NAMES', 'fen']
