import { bbox } from './6.5.0_turf.min.js';

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

export function fetchDataForHorse(thisHorse, mappy, repositionMap=true) {
	function mapData(data) {
		mappy.getSource('featured-data-source').setData(data);
        if (repositionMap) {
			const bounding_box = bbox(data);
			if (bounding_box[0] == Infinity) {
		 	    mappy.flyTo({
		 			center: mapParameters.center,
		 			zoom: mapParameters.zoom,
		 	        speed: .5,
		 	    });
			}
			else {
		         mappy.fitBounds(bounding_box, {
		             padding: 100,
		 	        speed: .5,
		         });							
			}
		}
	}
	thisHorse.closest('.border').addClass('highlight-carousel');
	return new Promise((resolve, reject) => {
		fetchDataFromLocalStorage(thisHorse.data('type'), thisHorse.data('id'), thisHorse.data('mode'))
			.then(data => {
				mapData(data);
				console.log(`${ thisHorse.data('type') } ${ thisHorse.data('id') } ${ thisHorse.data('mode') } retrieved from local storage.`);
				resolve(data);
			})
			.catch(() => {
				// Data not found in local storage, fetch from the network
				fetchDataFromNetwork(thisHorse.data('geometry_url'))
					.then(data => {
						mapData(data);
						localStorage.setItem(`${thisHorse.data('type')}_${thisHorse.data('id')}_${thisHorse.data('mode')}_data`, JSON.stringify(data));
						console.log(`${ thisHorse.data('type') } ${ thisHorse.data('id') } ${ thisHorse.data('mode') } fetched from the network and saved to local storage.`);
						resolve(data);
					})
					.catch(error => {
						console.error('Error fetching GeoJSON:', error);
						reject(error);
					});
			});
	});
}