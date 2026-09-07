"""Checks the Palette record and the JSON it writes.

The file stores only what cannot be recomputed. So the thing worth testing is that
everything it does store survives a round trip, and that everything it drops really does
come back the same when derived again.
"""

import json

import numpy as np
import pytest

from palette_lab import color
from palette_lab import palette as palette_module
from palette_lab.palette import BINDING_TOLERANCE
from palette_lab.palette import Palette
from palette_lab.search import Layout


def test_palette_rejects_a_wrong_shaped_array():
    with pytest.raises(ValueError, match=r"\(12, 3\)"):
        Palette(layout=Layout((6, 6)), oklch=np.zeros((11, 3)))


def test_derived_values_agree_with_a_fresh_computation(palette):
    linear = color.oklab_to_linear_srgb(color.oklch_to_oklab(palette.oklch))
    assert np.abs(palette.linear_srgb - linear).max() < 1e-12
    assert palette.hexes == color.to_hex(linear)

    pairs = color.pairwise_delta_e(color.linear_srgb_to_lab(linear))
    assert palette.min_delta_e == pytest.approx(float(pairs.min()))
    assert palette.mean_delta_e == pytest.approx(float(pairs.mean()))

    matrix = palette.delta_e_matrix
    assert matrix.shape == (12, 12)
    assert np.abs(matrix - matrix.T).max() == 0.0
    assert np.abs(np.diagonal(matrix)).max() == 0.0


def test_rings_report_the_shared_lightness_and_chroma(palette):
    ring_of_color = palette.layout.ring_of_color
    assert len(palette.rings) == palette.layout.n_rings
    for ring, (lightness, chroma) in enumerate(palette.rings):
        members = ring_of_color == ring
        assert palette.oklch[members, 0] == pytest.approx(lightness)
        assert palette.oklch[members, 1] == pytest.approx(chroma)
    # Rings in one chroma slot report one chroma between them, however many they are.
    for slot in range(palette.layout.n_chroma):
        members = [ring for ring in range(palette.layout.n_rings) if palette.layout.groups[ring] == slot]
        assert len({round(palette.rings[ring][1], 12) for ring in members}) == 1


def test_binding_pairs_are_exactly_the_pairs_at_the_minimum(palette):
    matrix = palette.delta_e_matrix
    limit = palette.min_delta_e + BINDING_TOLERANCE
    expected = {(row, col) for row in range(12) for col in range(row + 1, 12) if matrix[row, col] <= limit}

    assert set(palette.binding_pairs) == expected
    assert expected, "a valid palette always has at least one pair at the minimum"
    assert len(palette.binding_pairs) == len(set(palette.binding_pairs))
    for row, column in palette.binding_pairs:
        assert row < column, "binding pairs live in the upper triangle"


def test_quantized_separation_sits_just_below_the_exact_one(palette):
    # 8-bit rounding moves a color only slightly, so it can only cost a little.
    assert palette.min_delta_e - palette.min_delta_e_quantized < 1.0
    recomputed = color.pairwise_delta_e(color.linear_srgb_to_lab(color.from_hex(palette.hexes))).min()
    assert palette.min_delta_e_quantized == pytest.approx(float(recomputed))


def test_save_and_load_round_trip(palette, tmp_path):
    path = tmp_path / "nested" / f"{palette.layout.slug}.json"
    palette_module.save(palette, path)
    restored = palette_module.load(path)

    assert restored.layout == palette.layout
    assert np.abs(restored.oklch - palette.oklch).max() < 1e-6
    assert restored.hexes == palette.hexes
    assert restored.generated == palette.generated
    assert restored.config == palette.config
    # Everything the file dropped comes back identical from what it kept.
    assert restored.min_delta_e == pytest.approx(palette.min_delta_e, abs=1e-3)
    assert set(restored.binding_pairs) == set(palette.binding_pairs)


def test_the_file_holds_only_what_it_should(palette, tmp_path):
    path = tmp_path / "one.json"
    palette_module.save(palette, path)
    document = json.loads(path.read_text(encoding="utf-8"))

    assert set(document) == {"schema", "generated", "experiment", "result", "rings", "colors"}
    assert set(document["result"]) == {"min_de2000", "min_de2000_quantized"}
    assert set(document["colors"][0]) == {"ring", "hex", "oklch"}
    assert set(document["rings"][0]) == {"L", "C"}
    # Derived bulk stays out. de_matrix alone was most of the old 76 KB file.
    for dropped in ("de_matrix", "binding_pairs", "worst_pair", "best", "mean_de2000"):
        assert dropped not in json.dumps(document)
    assert path.stat().st_size < 4000


def test_stored_result_matches_what_a_reader_recomputes(palette, tmp_path):
    """The two stored numbers are the only place the file could drift from the palette.

    They are derived from the quantized palette, which is the one that gets written, so a
    reader who loads the file and recomputes must land on exactly the stored values.
    """
    path = tmp_path / "one.json"
    palette_module.save(palette, path)
    document = json.loads(path.read_text(encoding="utf-8"))
    restored = palette_module.load(path)

    assert document["result"]["min_de2000"] == round(restored.min_delta_e, 4)
    assert document["result"]["min_de2000_quantized"] == round(restored.min_delta_e_quantized, 4)
    # Quantization moves chroma by under 1e-6, so the numbers barely move from the original.
    assert restored.min_delta_e == pytest.approx(palette.min_delta_e, abs=1e-3)


def test_quantizing_keeps_the_palette_in_gamut(palette):
    """Rounding L moves the gamut boundary, so chroma is re-derived rather than rounded."""
    quantized = palette_module.quantize(palette)
    assert quantized.gamut_excess() == 0.0
    assert np.all(quantized.oklch[:, 1] <= palette.oklch[:, 1] + 1e-12), "chroma may only move inward"
    assert np.abs(quantized.oklch - palette.oklch).max() < 1e-5
    # Quantizing twice must not move it again, or load-then-save would drift.
    assert np.array_equal(palette_module.quantize(quantized).oklch, quantized.oklch)


def test_saving_refuses_an_out_of_gamut_palette(tmp_path):
    """quantize clamps chroma, so the check has to run before it or a real bug slips through."""
    layout = Layout((6, 6))
    oklch = np.stack([np.full(12, 0.7), np.full(12, 0.4), np.linspace(0, 360, 12, endpoint=False)], axis=-1)
    with pytest.raises(ValueError, match="out-of-gamut"):
        palette_module.save(Palette(layout=layout, oklch=oklch), tmp_path / "bad.json")
    assert not (tmp_path / "bad.json").exists()


def test_load_rejects_a_foreign_schema(tmp_path):
    path = tmp_path / "old.json"
    path.write_text(json.dumps({"schema": 1, "colors": []}), encoding="utf-8")
    with pytest.raises(ValueError, match="schema"):
        palette_module.load(path)


def test_a_schema_3_file_still_loads(tmp_path, palette):
    """Version 3 predates chroma groups, so its slots come from `shared_chroma`."""
    document = palette_module.to_document(palette)
    document["schema"] = 3
    del document["experiment"]["chroma_groups"]
    del document["experiment"]["lightness_floor"]
    path = tmp_path / "v3.json"
    path.write_text(json.dumps(document), encoding="utf-8")

    restored = palette_module.load(path)
    assert restored.layout.sizes == palette.layout.sizes
    assert restored.layout.shared_chroma == palette.layout.shared_chroma
    assert restored.config == palette.config
    if not palette.layout.chroma_groups or palette.layout.groups == Layout(palette.layout.sizes).groups:
        assert restored.layout.groups == palette.layout.groups


def test_slug_is_a_usable_filename():
    assert Layout((6, 6)).slug == "6+6"
    assert Layout((5, 7)).slug == "5+7"
    # ":" is what the layout name uses for shared chroma, and Windows will not take it.
    assert Layout((6, 6), shared_chroma=True).name == "6+6:C"
    assert Layout((6, 6), shared_chroma=True).slug == "6+6-sharedC"
    assert ":" not in Layout((6, 6), shared_chroma=True).slug
