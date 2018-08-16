# -*- coding: utf-8 -*-


def parse_env_file(env_file):
    envs = []
    desc_lines = []
    comment_block = False
    with open(env_file) as f:
        for line in (l.strip() for l in f if l.strip()):
            sign = line.split()[0]
            if sign in ('##', '#!'):
                comment_block = not comment_block
                if sign == '#!':
                    desc_lines = [line]
                continue
            if len(desc_lines) == 1 and desc_lines[0] == '#!':
                comment_block = not comment_block
                desc_lines = []
                continue
            if comment_block:
                continue
            if sign in ('#', '#?'):
                desc_lines.append(line)
                continue
            name, data = line.split('=', 1)
            if any(True for dl in desc_lines if dl.split()[0] == '#?'):
                data = 'скрыто'
            desc = ' '.join(dl.strip('#?') for dl in desc_lines)

            if '|' in desc:
                desc, meta = desc.split('|', 1)
                meta = {
                    m.split('=')[0].strip(): m.split('=')[1]
                    for m in meta.split(';') if m
                }
            else:
                meta = {}
            meta = {
                'default': meta.get('d'),
                'required': meta.get('r'),
                'type': meta.get('t'),
            }

            envs.append({
                'name': name,
                'data': data,
                'description': desc,
                **meta,
            })
            desc_lines = []
    return envs
