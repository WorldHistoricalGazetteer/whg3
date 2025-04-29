// /whg/webpack/js/localGeometryStorage.js


function fetchDataFromNetwork(url) {
    return fetch(url)
        .then(response => {
            if (!response.ok) {
                throw new Error('Bad network response.');
            }
            return response.json();
        });
}

export async function fetchDataForHorse(thisHorse, whg_map, repositionMap = true) {
    async function mapData(data) {
        return new Promise((resolve) => {

            whg_map.layersetObjects.forEach(layerset => {
                if (layerset?._source?.metadata) {
                    layerset?._layerIDs.forEach(layerID => {
                        if (whg_map.getLayer(layerID)) whg_map.removeLayer(layerID);
                    });
                    layerset?._sourceIDs.forEach(sourceID => {
                        if (whg_map.getSource(sourceID)) whg_map.removeSource(sourceID);
                    });
                }
            });

            whg_map.newSource(data);

            whg_map.once('sourcedata', () => {
                whg_map.setProjection({type: data?.metadata?.globeMode ? 'globe' : 'mercator'});
                whg_map.newLayerset(null, data);
                whg_map.once('sourcedata', () => {
                    if (repositionMap) {
                        if (data?.metadata?.extent) {
                            const extent = data.metadata.extent; // [minX, minY, maxX, maxY]
                            whg_map.fitBounds([
                                [extent[0], extent[1]], // southwest corner
                                [extent[2], extent[3]]  // northeast corner
                            ], {
                                padding: {
                                    bottom: $('.carousel-container').outerHeight() + 10 || 0,
                                }
                            });
                        }
                    }
                    resolve();
                });
            });


        });
    }

    $('#map').spin();
    thisHorse.closest('.border').addClass('highlight-carousel');
    try {
        const data = await fetchDataFromNetwork(`/mapdata/${thisHorse.data('type')}s/${thisHorse.data('id')}/carousel/`);
        return await mapData(data);
    } catch (error) {
        console.error('Error fetching GeoJSON:', error);
        throw error;
    } finally {
        $('#map').stopSpin();
    }
}
