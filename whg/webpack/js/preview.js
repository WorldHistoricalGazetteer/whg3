document.addEventListener("DOMContentLoaded", () => {
    const params = new URLSearchParams(window.location.search);
    const geojsonStr = params.get("data");
    const geojson = geojsonStr
        ? JSON.parse(decodeURIComponent(geojsonStr))
        : {type: "FeatureCollection", features: []};

    const map = new maplibregl.Map({
        container: "map",
        style: "https://tiles.whgazetteer.org/styles/WHG/style.json",
        center: [0, 0],
        zoom: 2
    });

    map.on("load", () => {

        map.addControl(new maplibregl.NavigationControl(), "top-right")
        .addControl(new maplibregl.GlobeControl(), 'top-right')
        .setProjection({ type: 'globe' })
            .addSource("places", { // ADD WHG ATTRIBUTION
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

        if (geojson.features.length) {
            const bounds = geojson.features.reduce(
                (b, f) => b.extend(f.geometry.coordinates),
                new maplibregl.LngLatBounds(
                    geojson.features[0].geometry.coordinates,
                    geojson.features[0].geometry.coordinates
                )
            );
            map.fitBounds(bounds, {padding: 20});
        }
    });
});
