// /whg/webpack/js/localGeometryStorage.js

import featuredDataLayers from './featuredDataLayerStyles';

function fetchDataFromLocalStorage(type, id, mode) {
	return new Promise((resolve, reject) => {
		const storedData = localStorage.getItem(`${type}_${id}_${mode}_data`);
		if (storedData) {
			resolve(JSON.parse(storedData));
		} else {
			reject(new Error('Data not found in local storage'));
		}
	});
}

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
			// console.log('thisHorse in fetchDataForHorse()', thisHorse);
			const hasTilesets = !!data.tilesets && data.tilesets.length > 0;
			
			var layersToRemove = whg_map.getStyle().layers.filter(layer => !!layer.source && layer.source == 'featured-data-source');
			layersToRemove.forEach(layer => {
			    whg_map.removeLayer(layer.id);
			});
			if (whg_map.getSource('featured-data-source')) whg_map.removeSource('featured-data-source');
			whg_map.newSource({...data, ds_id:'featured-data-source'});
			
			whg_map.once('sourcedata', () => {
				featuredDataLayers[data.mode == 'heatmap' ? 'heatmap' : 'default'].forEach(layer => {
					// data is a FeatureCollection here, no dataset or collection id
				    whg_map.addLayer({...layer, 'source-layer': hasTilesets ? 'features' : ''});
				});				
				if (hasTilesets) {
					whg_map.fitViewport(whg_map.tileBounds);
					/*whg_map.fitBounds(whg_map.tileBounds, {
                        padding: 100,
                        speed: 0.5,
                    });*/
					resolve();
				}
				else {
		            whg_map.once('sourcedata', () => {
		                if (repositionMap) {
		                    const bounding_box = bbox(data);
		                    if (bounding_box[0] == Infinity) {
		                        whg_map.reset();
		                    } else {	
								whg_map.fitViewport(bounding_box);				
		                        /*whg_map.fitBounds(bounding_box, {
		                            padding: 100,
		                            speed: 0.5,
		                        });*/
		                    }
		                }
		                resolve();
		            });
				}		
			});
		
			
        });
    }

    $('#map').spin();
    thisHorse.closest('.border').addClass('highlight-carousel');

    try {
        const data = await fetchDataFromLocalStorage(thisHorse.data('type'), thisHorse.data('id'), thisHorse.data('mode'));
        await mapData(data);
        console.log(`${thisHorse.data('type')} ${thisHorse.data('id')} ${thisHorse.data('mode')} retrieved from local storage.`);
        return data;
    } catch (error) {
        // Data not found in local storage, fetch from the network
        try {
            const data = await fetchDataFromNetwork(thisHorse.data('geometry_url'));
            await mapData(data);
			try {
				localStorage.setItem(`${thisHorse.data('type')}_${thisHorse.data('id')}_${thisHorse.data('mode')}_data`, JSON.stringify(data));
				console.log(`${ thisHorse.data('type') } ${ thisHorse.data('id') } ${ thisHorse.data('mode') } fetched from the network and saved to local storage.`);
			}
			catch(error) {
				console.log(`${ thisHorse.data('type') } ${ thisHorse.data('id') } ${ thisHorse.data('mode') } fetched from the network but failed to save to local storage.`);
			}
            return data;
        } catch (error) {
            console.error('Error fetching GeoJSON:', error);
            throw error;
        }
    } 
    finally {
    	$('#map').stopSpin();
    }
}
