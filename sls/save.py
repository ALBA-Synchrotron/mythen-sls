import numpy


def save(frame, filename):
    if filename.endswith('.raw'):
        data = '\n'.join('%d %d' % (n, p) for n, p in enumerate(frame))
        with open(filename, 'wt') as f:
            f.write(data)
    elif filename.endswith('.npy'):
        numpy.save(filename, frame)
    else:
        raise ValueError('Unsupported format')
