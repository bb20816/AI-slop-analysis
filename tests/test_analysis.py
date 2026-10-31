from datetime import date

import pandas as pd
import pytest

import analysis


def series(*points):
    return pd.DataFrame(
        {
            "date": pd.to_datetime([p[0] for p in points], format="ISO8601"),
            "activeness": [float(p[1]) for p in points],
        }
    )


def test_trend_converts_a_linear_rise_to_percent_of_mean_per_year():
    # 평균 2, 365.25일마다 1씩 증가 -> 평균의 50%/년
    df = series(("2020-01-01", 1), ("2020-12-31 06:00", 2), ("2021-12-31 12:00", 3))

    result = analysis.trend(df)

    assert result.slope_pct_per_year == pytest.approx(50.0, abs=0.01)
    assert result.points["index"].tolist() == pytest.approx([50.0, 100.0, 150.0])


def test_trend_is_independent_of_the_activeness_unit():
    small = series(("2020-01-01", 3), ("2021-01-01", 2), ("2022-01-01", 1))
    large = small.assign(activeness=small["activeness"] * 1e8)

    assert analysis.trend(small).slope_pct_per_year == pytest.approx(
        analysis.trend(large).slope_pct_per_year
    )


def test_trend_start_drops_earlier_rows_and_rebases_the_mean():
    df = series(("2020-01-01", 100), ("2021-01-01", 1), ("2022-01-01", 3))

    result = analysis.trend(df, start=date(2021, 1, 1))

    assert result.points["date"].min() == pd.Timestamp("2021-01-01")
    assert result.points["index"].tolist() == pytest.approx([50.0, 150.0])


def test_trend_end_drops_later_rows_and_keeps_the_end_date():
    df = series(("2020-01-01", 1), ("2021-01-01", 3), ("2022-01-01", 100))

    result = analysis.trend(df, end=date(2021, 1, 1))

    assert result.points["date"].max() == pd.Timestamp("2021-01-01")
    assert result.points["index"].tolist() == pytest.approx([50.0, 150.0])


def test_trend_rejects_a_range_with_fewer_than_two_points():
    df = series(("2020-01-01", 1), ("2021-01-01", 3))

    with pytest.raises(ValueError):
        analysis.trend(df, start=date(2020, 6, 1))


def test_analyze_applies_each_sites_own_range():
    rising = series(("2020-01-01", 1), ("2021-01-01", 2), ("2022-01-01", 3))
    falling = series(("2020-01-01", 3), ("2021-01-01", 2), ("2022-01-01", 1))
    sites = {"a": (rising, 1.0), "b": (falling, 2.0), "c": (rising, 3.0)}
    ranges = {
        "a": (date(2021, 1, 1), None),
        "b": (None, date(2021, 1, 1)),
        "c": (None, None),
    }

    result = analysis.analyze(sites, ranges)

    assert len(result.trends["a"].points) == 2
    assert result.trends["a"].points["date"].min() == pd.Timestamp("2021-01-01")
    assert len(result.trends["b"].points) == 2
    assert result.trends["b"].points["date"].max() == pd.Timestamp("2021-01-01")
    assert len(result.trends["c"].points) == 3


def test_trend_line_passes_through_the_mean_of_the_data():
    df = series(("2020-01-01", 1), ("2021-01-01", 5), ("2022-01-01", 3))

    result = analysis.trend(df)

    assert result.points["fit"].mean() == pytest.approx(100.0)


def test_correlation_is_positive_when_bigger_decline_goes_with_more_slop():
    slop = {"a": 1.0, "b": 2.0, "c": 3.0}
    slopes = {"a": -10.0, "b": -20.0, "c": -30.0}

    assert analysis.decline_slop_correlation(slopes, slop) == pytest.approx(1.0)


def test_correlation_is_negative_when_more_slop_goes_with_a_rise():
    slop = {"a": 1.0, "b": 2.0, "c": 3.0}
    slopes = {"a": -10.0, "b": 0.0, "c": 10.0}

    assert analysis.decline_slop_correlation(slopes, slop) == pytest.approx(-1.0)


def test_load_bluesky_computes_activeness_from_likes_and_posts_including_flagged_rows(tmp_path):
    # 첫 행의 활성화도 열(0.9)은 좋아요/게시물을 고친 뒤 갱신되지 않은 값이다.
    path = tmp_path / "bluesky.csv"
    path.write_bytes(
        b"date,num_likes,num_likers,num_posters,num_posts,num_follows,"
        b"num_followers,num_blocks,num_blockers,\xff\xfe(a),\xff\xfe\n"
        b"2026-10-30,8,1,1,2,1,1,1,1,,0.9\n"
        b"2023-03-01,5,1,1,10,1,1,1,1,a,70\n"
    )

    df = analysis.load_bluesky(path)

    assert df["date"].tolist() == [pd.Timestamp("2026-10-30"), pd.Timestamp("2023-03-01")]
    assert df["activeness"].tolist() == pytest.approx([2.0, 0.05])


def test_load_mastodon_parses_year_month_labels(tmp_path):
    path = tmp_path / "mastodon.csv"
    path.write_text(
        "month,mau,total_users,favourites_total_sample,favourites_mean,activeness,\n"
        "22-Sep,1,1,1,1,0.75,\n"
        "22-Nov,1,1,1,1,0.71,note\n",
        encoding="utf-8-sig",
    )

    df = analysis.load_mastodon(path)

    assert df["date"].tolist() == [pd.Timestamp("2022-09-01"), pd.Timestamp("2022-11-01")]
    assert df["activeness"].tolist() == [0.75, 0.71]


def test_load_steam_averages_each_day_before_applying_the_formula(tmp_path):
    path = tmp_path / "steam.csv"
    path.write_text(
        "2026-10-29 0:00,1000,100\n"
        "2026-10-30 10:00,1000,100\n"
        "2026-10-30 10:10,3000,300\n",
        encoding="utf-8-sig",
    )

    df = analysis.load_steam(path)

    # 10/30: 평균 접속자 2000, 평균 게임 중 200 -> 200 / 2000^2 = 5e-5
    assert df["date"].tolist() == [pd.Timestamp("2026-10-29"), pd.Timestamp("2026-10-30")]
    assert df["activeness"].tolist() == pytest.approx([1e-4, 5e-5])


def test_load_slop_average_reads_the_precomputed_cell(tmp_path):
    path = tmp_path / "slop.csv"
    path.write_text(
        "date,source,total_classified,ai_generated_count,human_count,"
        "uncertain_count,ai_percentage,,average ai_percentage\n"
        "2026-03-08,bluesky,69,6,63,0,8.6957,,12.99\n"
        "2026-03-09,bluesky,61,4,57,0,6.5574,,\n",
        encoding="utf-8",
    )

    assert analysis.load_slop_average(path) == 12.99


@pytest.mark.parametrize(
    ("start", "bluesky", "steam", "mastodon", "correlation"),
    [
        (None, -142.72, -6.30, -9.11, 0.973),
        (date(2024, 9, 7), 12.64, 0.16, -2.09, -0.997),
        (date(2026, 3, 8), 19.70, 28.74, 15.83, 0.011),
    ],
)
def test_real_data_matches_the_independent_calculation(
    start, bluesky, steam, mastodon, correlation
):
    # 기대값은 이 모듈을 쓰지 않고 표준 라이브러리로 따로 계산한 결과다.
    sites = analysis.load_sites()
    result = analysis.analyze(sites, {name: (start, None) for name in sites})

    assert result.slopes["Bluesky"] == pytest.approx(bluesky, abs=0.01)
    assert result.slopes["Steam"] == pytest.approx(steam, abs=0.01)
    assert result.slopes["Mastodon"] == pytest.approx(mastodon, abs=0.01)
    assert result.correlation == pytest.approx(correlation, abs=0.001)
