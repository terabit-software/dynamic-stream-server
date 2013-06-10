import re

_reg_cet = re.compile(r"LatLng\(\s*([\d\.-]+)\s*,\s*([\d\.-]+)\s*\)"
                      r".*?\n"
                      r".*?(\d+).*?'(.*?)'.*?'(.*?)'")

def parser(text):
    data = _reg_cet.findall(text)
    data = [
        {
            'id': int(x[2]),
            'geo': [float(i) for i in x[:2]],
            'name': x[3],
            'status': 'Desligado' not in x[-1]
        }
        for x in data
    ]

    return data