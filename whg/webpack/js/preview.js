document.addEventListener("DOMContentLoaded", () => {
    const geojson = window.geojson

    function extendBounds(bounds, coords) {
        if (typeof coords[0] === "number") {
            // [lng, lat]
            bounds.extend(coords);
        } else {
            coords.forEach(c => extendBounds(bounds, c));
        }
        return bounds;
    }

    let center = [0, 0];
    let zoom = 2;

    let bounds = null;
    if (geojson.features.length) {
        const initialCoords = geojson.features[0].geometry.coordinates;
        const bounds = geojson.features.reduce((b, f) => {
            return extendBounds(b, f.geometry.coordinates);
        }, new maplibregl.LngLatBounds(initialCoords, initialCoords));

        center = bounds.getCenter().toArray();
    }

    const map = new maplibregl.Map({
        container: "map",
        style: "https://tiles.whgazetteer.org/styles/WHG/style.json",
        center: center,
        zoom: zoom,
    });

    map.on("load", () => {

        map.addControl(new maplibregl.NavigationControl(), "top-right")
        .addControl(new maplibregl.GlobeControl(), 'top-right')
        .setProjection({ type: 'globe' })
            .addSource("places", {
            type: "geojson",
            data: geojson,
                attribution: 'Map data &copy; <a href="https://www.whgazetteer.org">World Historical Gazetteer</a> contributors'
        });

        // Point layer
        map.addLayer({
            id: "places-points",
            type: "circle",
            source: "places",
            filter: ["==", ["geometry-type"], "Point"],
            paint: {
                "circle-radius": 6,
                "circle-color": "#007cbf"
            }
        });

        // Line layer
        map.addLayer({
            id: "places-lines",
            type: "line",
            source: "places",
            filter: ["==", ["geometry-type"], "LineString"],
            paint: {
                "line-width": 2,
                "line-color": "#ff6600"
            }
        });

        // Polygon layer
        map.addLayer({
            id: "places-polygons",
            type: "fill",
            source: "places",
            filter: ["==", ["geometry-type"], "Polygon"],
            paint: {
                "fill-color": "#33aa33",
                "fill-opacity": 0.4
            }
        });

        if (bounds) {
            map.fitBounds(bounds, { padding: 20 });
        }
    });
});
