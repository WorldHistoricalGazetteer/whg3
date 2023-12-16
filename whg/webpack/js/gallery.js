
import '../../../static/admin/css/vendor/select2/select2.min.css';
import '../../../static/admin/js/vendor/select2/select2.full.min.js';
import throttle from 'lodash/throttle';
import { bbox } from './6.5.0_turf.min.js';
import { attributionString, startSpinner } from './utilities';
import { CustomAttributionControl } from './customMapControls';
import featuredDataLayers from './featuredDataLayerStyles';
import { fetchDataForHorse } from './localGeometryStorage';

import '../css/maplibre-common.css';
import '../css/gallery.css';


let style_code;
if (mapParameters.styleFilter.length == 0) {
	style_code = ['DATAVIZ', 'DEFAULT']
} else {
	style_code = mapParameters.styleFilter[0].split(".");
}

maptilersdk.config.apiKey = mapParameters.mapTilerKey;
let mappy = new maptilersdk.Map({
	container: mapParameters.container,
	center: mapParameters.center,
	zoom: mapParameters.zoom,
	minZoom: mapParameters.minZoom,
	maxZoom: mapParameters.maxZoom,
	style: maptilersdk.MapStyle[style_code[0]][style_code[1]],
	attributionControl: false,
	geolocateControl: false,
	navigationControl: mapParameters.controls.navigation,
	userProperties: true,
	bearing: 0,
	pitch: 0,
});

let nullCollection = {
    type: 'FeatureCollection',
    features: []
}

var datasetLayers = [
	{
		'id': 'country_polygons',
		'type': 'fill',
		'source': 'places',
		'paint': {
			'fill-color': 'rgba(0,128,0,.4)', // green,
			'fill-outline-color': 'red',
		},
		'filter': ['==', '$type', 'Polygon']
	}
]

let page = 1;
let datacollection = 'datasets'

function waitMapLoad() {
    return new Promise((resolve) => {
        mappy.on('load', () => {
            console.log('Map loaded.');
            
            mappy.addSource('places', {
				'type': 'geojson',
			    'data': nullCollection,
				'attribution': attributionString(),
			});
			
		    datasetLayers.forEach(layer => {
				mappy.addLayer(layer);
			});
	
			mappy.addSource('featured-data-source', {
			    type: 'geojson',
			    data: nullCollection
			});
			
			featuredDataLayers.forEach(layer => {
				mappy.addLayer(layer);
			});
			
			mappy.addControl(new CustomAttributionControl({
				compact: true,
		    	autoClose: mapParameters.controls.attribution.open === false,
			}), 'bottom-right');	
            
            resolve();
        });
    });
}

function waitDocumentReady() {
    return new Promise((resolve) => {
        $(document).ready(() => resolve());
    });
}

function buildGallery(datacollections) {
    
    var dynamicGallery = $('#dynamic-gallery');
    dynamicGallery.empty();

    datacollections.forEach(function(dc) {
    	
        var dsCard = $('<div>', {'class': 'col-md-4 mt-1'});
        var dsCardGallery = $('<div>', {'class': 'ds-card-gallery'});
        var dsCardContent = $('<div>', {'class': 'ds-card-content', 'data-id': dc.ds_or_c_id});
        var dsCardTitle = $('<h6>', {'class': 'ds-card-title', text: dc.title});
        var dsCardBlurb = $('<p>', {'class': 'ds-card-blurb my-1'});
        var dsCardImage = $('<img>', {'src': dc.image_file, 'width': '60', 'class': 'float-end'});
        var dsCardDescription = $('<span>', {html: dc.description});
        var dsCardCreator = $('<p>', {'class': 'ds-card-creator', text: dc.creator});
        var dsCardOwner = $('<p>', {'class': 'ds-card-owner', text: dc.owner});

        dsCardBlurb.append(dsCardImage);
        dsCardBlurb.append(dsCardDescription);

        dsCardContent.append(dsCardTitle);
        dsCardContent.append(dsCardBlurb);
        dsCardContent.append(dsCardCreator);
        dsCardContent.append(dsCardOwner);

        dsCardGallery.append(dsCardContent)
        .data({
			'type':dc.type,
			'id':dc.ds_or_c_id,
			'mode':dc.display_mode,
			'geometry_url':dc.geometry_url
		});
        dsCard.append(dsCardGallery);

        dynamicGallery.append(dsCard);
    });
	
}

Promise.all([waitMapLoad(), waitDocumentReady()])
    .then(() => {
	
	const throttledUpdates = throttle(() => { // Uses imported lodash function
	    fetchData();
	    updateAreaMap();
	}, 400);    
	
    const countryDropdown = $('#countryDropdown');
    countryDropdown.select2({
        data: dropdown_data,
        width: 'element', // Use CSS rules
        placeholder: $(this).data('placeholder'),
        closeOnSelect: false,
        allowClear: true,
    }).on('select2:selecting', function (e) {
        if(!!e.params.args.data['ccodes']) { // Region selected: add countries from its ccodes
        	e.preventDefault();
        	let ccodes = Array.from(new Set([...e.params.args.data['ccodes'], ...countryDropdown.select2('data').map(country => country.id)]));
        	countryDropdown.val(ccodes).trigger('change');
        }
    }).on('change', function (e) {
		throttledUpdates();
    });
    
    function fetchData() {
		const sort = ($('#reverseSortCheckbox').prop('checked') ? '-' : '') + $('#sortDropdown').val();
    	const countries = countryDropdown.select2('data').map(country => country.id).join(',');
    	const search = $('#searchInput').val();
    	const url = `/api/gallery/${datacollection}/?page=${page}&sort=${sort}&countries=${countries}&q=${search}`;
    	console.log(`Fetching from: ${url}`);
        fetch(url)
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! Status: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            console.log('Fetched data:', data);
            buildGallery(data.items);
            const $select = $('#page_controls select');
            $select.empty();
		    for (let i = 1; i <= data.total_pages; i++) {
		      const $option = $(`<option value=${i}>page ${i} of ${data.total_pages}</option>`);
		      $select.append($option);
		    }
        })
        .catch(error => {
            console.error('Fetch error:', error);
        });
    }
    
    throttledUpdates(); // Fetch and build initial gallery; set map filter
    
    function resetMap() {
		mappy.flyTo({
 			center: mapParameters.center,
 			zoom: mapParameters.zoom,
 	        speed: .5,
 	    });
	}
    
    function updateAreaMap() {
    	const countries = countryDropdown.select2('data').map(country => country.id);
    	const filteredCountries = {
			type: 'FeatureCollection',
			features: country_feature_collection['features'].filter(feature => {
				const countryCode = feature.properties.ccode;
				return countries.includes(countryCode);
			}),
		};
		
		mappy.getSource('places').setData(filteredCountries);
		try {
			mappy.fitBounds(bbox(filteredCountries), {
		        padding: 30,
		        maxZoom: 7,
		        duration: 1000,
		    });
		}
		catch {
			resetMap();
		}
    }
    
    $('#galleryTabs .nav-link').on('click', function() {
		datacollection = $(this).attr('href').substring(1);
		fetchData();
    });
    
    $('#sortDropdown, #reverseSortCheckbox, #searchInput').on('change', function () {
        fetchData();
    });
    
    $('body').on('mouseenter', '.ds-card-gallery', (e) => {
		fetchDataForHorse($(e.target), mappy);
	}).on('mouseleave', '.ds-card-gallery', (e) => {
		mappy.getSource('featured-data-source').setData(nullCollection);
		resetMap();
	});
    
});