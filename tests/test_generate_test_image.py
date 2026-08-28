from generate_test_image import component_offset, generate, image_offset


def test_generate_returns_expected_size():
    img = generate(0)
    assert img.size == (400, 300)


def test_generate_is_deterministic_per_variant():
    assert generate(0).tobytes() == generate(0).tobytes()


def test_different_variants_differ():
    assert generate(0).tobytes() != generate(1).tobytes()


def test_output_component_offset_is_zero():
    assert component_offset("output") == 0


def test_other_components_get_distinct_offsets():
    assert component_offset("button") != component_offset("dialog")


def test_default_image_offset_is_zero():
    assert image_offset("default") == 0


def test_other_images_get_distinct_offsets():
    assert image_offset("hover") != image_offset("pressed")
