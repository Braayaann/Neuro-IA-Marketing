from types import SimpleNamespace

import pytest

from backend.metrics import quadrant_times
from backend.models import Observation, db
from conftest import login, make_study


def sample(elapsed, x=0.1, y=0.1, ad_id=1, valid=True):
    return SimpleNamespace(elapsed=elapsed, x=x, y=y, study_ad_id=ad_id, valid=valid)


@pytest.mark.parametrize(('count', 'columns', 'rows'), [(1, 1, 1), (2, 2, 1), (3, 3, 1), (3, 2, 2), (4, 2, 2)])
def test_quadrants_are_relative_to_each_ad(count, columns, rows):
    slots = [SimpleNamespace(id=i + 1, position=i) for i in range(count)]
    observations = []
    elapsed = 0
    for slot in slots:
        for x, y in [(0.25, 0.25), (0.75, 0.25), (0.25, 0.75), (0.75, 0.75)]:
            screen_x = (slot.position % columns + x) / columns
            screen_y = (slot.position // columns + y) / rows
            for _ in range(2):
                observations.append(sample(elapsed, screen_x, screen_y, slot.id))
                elapsed += 0.5
    assert quadrant_times(observations, slots, columns) == {
        slot.id: [0.5, 0.5, 0.5, 0.5] for slot in slots
    }


@pytest.mark.parametrize('middle', [
    sample(0.5, valid=False),
    sample(0.5, x=None),
    sample(0.5, x=float('nan')),
    sample(0.5, x=1.1),
    sample(0.5, ad_id=None),
])
def test_invalid_sample_interrupts_interval(middle):
    observations = [sample(0), middle, sample(1), sample(1.5)]
    assert quadrant_times(observations, [SimpleNamespace(id=1, position=0)], 1)[1] == [0.5, 0, 0, 0]


@pytest.mark.parametrize(('interval', 'expected'), [(0, 0), (-0.5, 0), (1.5, 1.5), (1.5001, 0)])
def test_interval_limits(interval, expected):
    observations = [sample(0), sample(interval)]
    assert quadrant_times(observations, [SimpleNamespace(id=1, position=0)], 1)[1] == [expected, 0, 0, 0]


def test_midlines_and_screen_edges():
    slots = [SimpleNamespace(id=1, position=0)]
    observations = [sample(0, 0, 0), sample(0.5, 0, 0),
                    sample(1, 0.5, 0), sample(1.5, 0.5, 0),
                    sample(2, 0, 0.5), sample(2.5, 0, 0.5),
                    sample(3, 0.5, 0.5), sample(3.5, 1, 1)]
    assert quadrant_times(observations, slots, 1)[1] == [0.5] * 4


def test_results_derive_quadrants_from_saved_observations(app, client):
    headers = login(client)
    study = make_study(client, headers)
    sid = study['id']
    first, second = [slot['id'] for slot in study['slots']]
    empty = client.get(f'/api/studies/{sid}/results').json
    assert empty['quadrant_seconds'] == 0
    assert len(empty['ads'][0]['quadrants']) == 4

    # Dos columnas. x=0.3 pertenece a la mitad derecha del primer anuncio.
    readings = [
        (0, 0.1, 0.1, first, True, 0),
        (0.5, 0.1, 0.1, first, True, 0.5),
        (1, 0.3, 0.1, first, True, 0.5),  # cambia de cuadrante
        (1.5, 0.3, 0.1, first, True, 0.5),
        (2, None, None, None, False, 0),
        (2.5, 0.3, 0.1, first, True, 0),
        (3, 0.3, 0.1, first, True, 0.5),
        (5, 0.3, 0.1, first, True, 0),  # pausa larga
        (5.5, 0.3, 0.1, first, True, 0.5),
        (6, 0.8, 0.1, second, True, 0),  # cambia de anuncio
        (7.5, 0.8, 0.1, second, True, 1.5),
    ]
    with app.app_context():
        for seq, (elapsed, x, y, ad_id, valid, seconds) in enumerate(readings):
            db.session.add(Observation(study_id=sid, study_ad_id=ad_id, seq=seq,
                                       elapsed=elapsed, x=x, y=y, valid=valid,
                                       estimated_seconds=seconds))
        db.session.commit()

    response = client.get(f'/api/studies/{sid}/results')
    assert response.status_code == 200
    result = response.json
    assert result['estimated_seconds'] == 4
    assert result['quadrant_seconds'] == 3.5
    ads = {ad['id']: ad for ad in result['ads']}
    assert ads[first]['seconds'] == 2.5
    assert len(ads[first]['points']) == 8
    assert all(point['x'] < 0.5 for point in ads[first]['points'])
    assert len(ads[second]['points']) == 2
    assert ads[first]['quadrant_seconds'] == 2
    assert ads[first]['quadrants'] == [
        {'key': 'top_left', 'label': 'Superior izquierdo', 'seconds': 0.5},
        {'key': 'top_right', 'label': 'Superior derecho', 'seconds': 1.5},
        {'key': 'bottom_left', 'label': 'Inferior izquierdo', 'seconds': 0},
        {'key': 'bottom_right', 'label': 'Inferior derecho', 'seconds': 0},
    ]
    assert ads[second]['seconds'] == ads[second]['quadrant_seconds'] == 1.5
