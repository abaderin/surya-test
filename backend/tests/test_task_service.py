import uuid

from app.services.task_service import (
    color_for_block_type,
    ocr_block_ids_from_payload,
    should_enqueue_image_extraction,
    should_enqueue_ocr,
)


def test_color_for_block_type_maps_surya_labels() -> None:
    assert color_for_block_type("Text") == "blue"
    assert color_for_block_type("SectionHeader") == "red"
    assert color_for_block_type("Picture") == "green"
    assert color_for_block_type("Caption") == "orange"
    assert color_for_block_type("PageFooter") == "gray"
    assert color_for_block_type("Table") == "purple"
    assert color_for_block_type("UnknownLabel") == "gray"


def test_should_enqueue_ocr_for_supported_labels() -> None:
    assert should_enqueue_ocr("Text") is True
    assert should_enqueue_ocr("SectionHeader") is True
    assert should_enqueue_ocr("ListItem") is True
    assert should_enqueue_ocr("PageHeader") is True
    assert should_enqueue_ocr("Equation") is True
    assert should_enqueue_ocr("Caption") is True
    assert should_enqueue_ocr("Footnote") is True
    assert should_enqueue_ocr("Code") is True
    assert should_enqueue_ocr("Form") is True
    assert should_enqueue_ocr(" sectionheader ") is True
    assert should_enqueue_ocr("Picture") is False
    assert should_enqueue_ocr("Table") is False
    assert should_enqueue_ocr("UnknownLabel") is False


def test_should_enqueue_image_extraction_only_for_picture_label() -> None:
    assert should_enqueue_image_extraction("Picture") is True
    assert should_enqueue_image_extraction("Figure") is False
    assert should_enqueue_image_extraction("Text") is False


def test_ocr_block_ids_from_payload_supports_new_block_ids() -> None:
    first = uuid.uuid4()
    second = uuid.uuid4()
    assert ocr_block_ids_from_payload({"block_ids": [str(first), str(second)]}) == [first, second]


def test_ocr_block_ids_from_payload_supports_legacy_block_id() -> None:
    value = uuid.uuid4()
    assert ocr_block_ids_from_payload({"block_id": str(value)}) == [value]
