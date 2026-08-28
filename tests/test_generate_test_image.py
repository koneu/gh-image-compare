from generate_test_image import generate


def test_generate_returns_expected_size():
    img = generate(0)
    assert img.size == (400, 300)


def test_generate_is_deterministic_per_variant():
    assert generate(0).tobytes() == generate(0).tobytes()


def test_different_variants_differ():
    assert generate(0).tobytes() != generate(1).tobytes()
