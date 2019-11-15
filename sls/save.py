import numpy


def save(frame, filename):
    if filename.endswith('.raw'):
        data = '\n'.join('{} {}'.format(n, p) for n, p in enumerate(frame))
        with open(filename, 'wt') as f:
            f.write(data)
    else:
        raise ValueError('Unsupported format')
