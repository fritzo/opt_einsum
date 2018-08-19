import numpy as np
import pytest

from opt_einsum import contract, contract_path, get_symbol, shared_intermediates


def test_shared_backend():
    w = np.random.normal(size=(2, 3, 4))
    x = np.random.normal(size=(3, 4, 5))
    y = np.random.normal(size=(4, 5, 6))
    z = np.random.normal(size=(5, 6, 7))
    expr = 'abc,bcd,cde,def->af'

    expected = contract(expr, w, x, y, z, backend='torch')
    with shared_intermediates():
        actual = contract(expr, w, x, y, z, backend='torch')

    assert (actual == expected).all()


@pytest.mark.parametrize('backend', ['torch', 'numpy'])
def test_complete_sharing(backend):
    x = np.random.normal(size=(5, 4))
    y = np.random.normal(size=(4, 3))
    z = np.random.normal(size=(3, 2))

    print('-' * 40)
    print('Without sharing:')
    with shared_intermediates() as cache:
        contract('ab,bc,cd->', x, y, z, backend=backend)
        expected = len(cache)

    print('-' * 40)
    print('With sharing:')
    with shared_intermediates() as cache:
        contract('ab,bc,cd->', x, y, z, backend=backend)
        contract('ab,bc,cd->', x, y, z, backend=backend)
        actual = len(cache)

    print('-' * 40)
    print('Without sharing: {} expressions'.format(expected))
    print('With sharing: {} expressions'.format(actual))
    assert actual == expected


@pytest.mark.parametrize('backend', ['torch', 'numpy'])
def test_partial_sharing(backend):
    x = np.random.normal(size=(5, 4))
    y = np.random.normal(size=(4, 3))
    z1 = np.random.normal(size=(3, 2))
    z2 = np.random.normal(size=(3, 2))

    print('-' * 40)
    print('Without sharing:')
    num_exprs_nosharing = 0
    with shared_intermediates() as cache:
        contract('ab,bc,cd->', x, y, z1, backend=backend)
        num_exprs_nosharing += len(cache) - 3  # ignore shared_tensor
    with shared_intermediates() as cache:
        contract('ab,bc,cd->', x, y, z2, backend=backend)
        num_exprs_nosharing += len(cache) - 3  # ignore shared_tensor

    print('-' * 40)
    print('With sharing:')
    with shared_intermediates() as cache:
        contract('ab,bc,cd->', x, y, z1, backend=backend)
        contract('ab,bc,cd->', x, y, z2, backend=backend)
        num_exprs_sharing = len(cache) - 4  # ignore shared_tensor

    print('-' * 40)
    print('Without sharing: {} expressions'.format(num_exprs_nosharing))
    print('With sharing: {} expressions'.format(num_exprs_sharing))
    assert num_exprs_nosharing > num_exprs_sharing


def compute_cost(cache):
    return sum(1 for key in cache.keys() if key[0] in ('einsum', 'tensordot'))


@pytest.mark.parametrize('size', [3, 4, 5])
def test_chain(size):
    xs = [np.random.normal(size=(2, 2)) for _ in range(size)]
    alphabet = ''.join(get_symbol(i) for i in range(size + 1))
    names = [alphabet[i:i+2] for i in range(size)]
    inputs = ','.join(names)

    with shared_intermediates():
        print(inputs)
        for i in range(size + 1):
            target = alphabet[i]
            equation = '{}->{}'.format(inputs, target)
            path_info = contract_path(equation, *xs)
            print(path_info[1])
            contract(equation, *xs, backend='torch')
        print('-' * 40)


@pytest.mark.parametrize('size', [3, 4, 5, 10])
def test_chain_2(size):
    xs = [np.random.normal(size=(2, 2)) for _ in range(size)]
    alphabet = ''.join(get_symbol(i) for i in range(size + 1))
    names = [alphabet[i:i+2] for i in range(size)]
    inputs = ','.join(names)

    with shared_intermediates():
        print(inputs)
        for i in range(size):
            target = alphabet[i:i+2]
            equation = '{}->{}'.format(inputs, target)
            path_info = contract_path(equation, *xs)
            print(path_info[1])
            contract(equation, *xs, backend='torch')
        print('-' * 40)


def test_chain_2_growth():
    sizes = list(range(1, 21))
    costs = []
    for size in sizes:
        xs = [np.random.normal(size=(2, 2)) for _ in range(size)]
        alphabet = ''.join(get_symbol(i) for i in range(size + 1))
        names = [alphabet[i:i+2] for i in range(size)]
        inputs = ','.join(names)

        with shared_intermediates() as cache:
            for i in range(size):
                target = alphabet[i:i+2]
                equation = '{}->{}'.format(inputs, target)
                contract(equation, *xs, backend='torch')
            costs.append(compute_cost(cache))

    print('sizes = {}'.format(repr(sizes)))
    print('costs = {}'.format(repr(costs)))
    for size, cost in zip(sizes, costs):
        print('{}\t{}'.format(size, cost))


@pytest.mark.parametrize('size', [3, 4, 5])
def test_chain_sharing(size):
    xs = [np.random.normal(size=(2, 2)) for _ in range(size)]
    alphabet = ''.join(get_symbol(i) for i in range(size + 1))
    names = [alphabet[i:i+2] for i in range(size)]
    inputs = ','.join(names)

    num_exprs_nosharing = 0
    for i in range(size + 1):
        with shared_intermediates() as cache:
            target = alphabet[i]
            equation = '{}->{}'.format(inputs, target)
            contract(equation, *xs, backend='torch')
            num_exprs_nosharing += compute_cost(cache)

    with shared_intermediates() as cache:
        print(inputs)
        for i in range(size + 1):
            target = alphabet[i]
            equation = '{}->{}'.format(inputs, target)
            path_info = contract_path(equation, *xs)
            print(path_info[1])
            contract(equation, *xs, backend='torch')
        num_exprs_sharing = compute_cost(cache)

    print('-' * 40)
    print('Without sharing: {} expressions'.format(num_exprs_nosharing))
    print('With sharing: {} expressions'.format(num_exprs_sharing))
    assert num_exprs_nosharing > num_exprs_sharing