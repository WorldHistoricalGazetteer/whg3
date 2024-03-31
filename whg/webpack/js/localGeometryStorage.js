// /whg/webpack/js/localGeometryStorage.js

import { startSpinner } from './utilities';
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

export async function fetchDataForHorse(thisHorse, mappy, repositionMap = true) {
    async function mapData(data) {
        return new Promise((resolve) => {
			
			const hasTilesets = !!data.tilesets && data.tilesets.length > 0;
			
			var layersToRemove = mappy.getStyle().layers.filter(layer => !!layer.source && layer.source == 'featured-data-source');
			layersToRemove.forEach(layer => {
			    mappy.removeLayer(layer.id);
			});
			if (mappy.getSource('featured-data-source')) mappy.removeSource('featured-data-source');
			mappy.newSource({...data, ds_id:'featured-data-source'});
			
			mappy.once('sourcedata', () => {
				featuredDataLayers[data.mode == 'heatmap' ? 'heatmap' : 'default'].forEach(layer => {
				    mappy.addLayer({...layer, 'source-layer': hasTilesets ? 'features' : ''});
				});				
				if (hasTilesets) {
					mappy.fitViewport(mappy.tileBounds);
					/*mappy.fitBounds(mappy.tileBounds, {
                        padding: 100,
                        speed: 0.5,
                    });*/
					resolve();
				}
				else {
		            mappy.once('sourcedata', () => {
		                if (repositionMap) {
		                    const bounding_box = bbox(data);
		                    if (bounding_box[0] == Infinity) {
		                        mappy.reset();
		                    } else {	
								mappy.fitViewport(bounding_box);				
		                        /*mappy.fitBounds(bounding_box, {
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

    const spinner_map = startSpinner("map", 1.5);
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
        spinner_map.stop();
    }
}
