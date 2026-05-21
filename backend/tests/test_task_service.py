from app.services.task_service import color_for_block_type, should_enqueue_ocr


def test_color_for_block_type_maps_surya_labels() -> None:
    assert color_for_block_type("Text") == "blue"
    assert color_for_block_type("SectionHeader") == "red"
    assert color_for_block_type("Picture") == "green"
    assert color_for_block_type("Caption") == "orange"
    assert color_for_block_type("PageFooter") == "gray"
    assert color_for_block_type("Table") == "purple"
    assert color_for_block_type("UnknownLabel") == "gray"


def test_should_enqueue_ocr_only_for_text_label() -> None:
    assert should_enqueue_ocr("Text") is True
    assert should_enqueue_ocr("SectionHeader") is False
    assert should_enqueue_ocr("ListItem") is False
