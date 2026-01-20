from __future__ import annotations

import pytest

from app.engine.rules_infer import predict_bid_and_trump_index


def test_predict_bid_and_trump_index_cases() -> None:
    cases = [
        # len(first)=1 -> bid 14; trump index 0
        ('[["A"],["K"],["Q"],["7"]]', (14, 0)),
        # len(first)=1 with extra jacks outside -> still 14; trump index 0
        ([["7"], ["J"], ["J"], ["A"]], (14, 0)),
        # len(first)=2, first is J but second not (9/A/10) => bid 14
        # trump picks second => index 1
        ('[["J","K"],["7"],["8"]]', (14, 1)),
        # len(first)=2, first not J => trump picks first => index 0
        ('[["A","K"],["7"],["8"]]', (14, 0)),
        # len(first)=2, J + 10 => base 15, plus 1 extra J outside => 16
        # trump picks second => index 1
        ('[["J","10"],["J"],["7"]]', (16, 1)),
        # len(first)=3, J and 9 present => bid 16; trump picks last => index 2
        ('[["J","9","7"],["A"]]', (16, 2)),
        # len(first)=3, J and (A or 10) and (K or Q) => bid 16; trump picks second => 1
        ('[["J","A","K"],["7"]]', (16, 1)),
        # len(first)=3, J and 10 and Q => bid 16; trump picks second => 1
        ('[["J","10","Q"],["7"]]', (16, 1)),
        # len(first)=3, J and (A or 10) but no K/Q => bid 15; trump picks second => 1
        ('[["J","10","8"],["7"]]', (15, 1)),
        # len(first)=3, J K Q => bid 15; trump picks second => 1
        ('[["J","K","Q"],["7"]]', (15, 1)),
        # len(first)=3, J present but no stronger combos => bid 14; trump picks second => 1
        ('[["J","8","7"],["A"]]', (14, 1)),
        # len(first)=3, 9 A K (no J) => bid 15; trump picks second => 1
        ('[["9","A","K"],["7"]]', (15, 1)),
        # len(first)=3 else => bid 14; trump picks second => 1
        ('[["A","K","Q"],["7"]]', (14, 1)),
        # len(first)=4, J + other point => bid 16; trump picks last => 3
        ('[["J","A","8","7"]]', (16, 3)),
        # len(first)=4, J only (no other point besides J) => bid 15; trump last => 3
        ('[["J","K","8","7"]]', (15, 3)),
        # len(first)=4, no J but has a point => bid 15; trump last => 3
        ('[["10","K","8","7"]]', (15, 3)),
        # len(first)=4, no points => bid 14; trump last => 3
        ('[["K","Q","8","7"]]', (14, 3)),
        # Extra-jacks increment (len(first)=2): base 15 +2 => 17; trump picks second => 1
        ('[["J","9"],["J"],["J"]]', (17, 1)),
        # Extra-jacks increment (len(first)=3): base 16 +2 => 18; trump last => 2
        ('[["J","9","7"],["J"],["J"]]', (18, 2)),
        ('[["J","A","10"],["J"]]', (17, 1)),
    ]

    for i, (ck, expected) in enumerate(cases, start=1):
        got = predict_bid_and_trump_index(ck)
        assert got == expected, (
            f"Case #{i} failed.\ncanonical_key={ck}\nexpected={expected}\ngot={got}"
        )


@pytest.mark.parametrize(
    "bad",
    [
        "",  # not JSON
        "[]",  # empty list
        "[[]]",  # empty group
        '{"not":"a list"}',  # wrong top-level type
    ],
)
def test_predict_bid_and_trump_index_bad_inputs(bad: str) -> None:
    with pytest.raises(Exception):
        predict_bid_and_trump_index(bad)