
import '../../../static/admin/css/vendor/select2/select2.min.css';
import '../../../static/admin/js/vendor/select2/select2.full.min.js';
import debounce from 'lodash/debounce';
import { bbox } from './6.5.0_turf.min.js';
import { attributionString } from './utilities';
import { CustomAttributionControl } from './customMapControls';
import featuredDataLayers from './featuredDataLayerStyles';
import { fetchDataForHorse } from './localGeometryStorage';
import { CountryCacheFeatureCollection } from  './countryCache';

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

let countryCache = new CountryCacheFeatureCollection();

let page = 1;
const $page_controls = $('#page_controls');	
let $select;

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
        $(document).ready(() => {			
			resolve();
		});
    });
}

function buildGallery(datacollections) {
    
    var dynamicGallery = $('#dynamic-gallery');
    dynamicGallery.empty();
    
    if (datacollections.length === 0) {
        var noResultsMessage = $('<h3>').text(`No matching ${datacollection} found`);
        dynamicGallery.append(noResultsMessage);
        noResultsMessage.after(
		    $('<p>').text('Try adjusting the filters.')
		);
    } else {
	    datacollections.forEach(function(dc) {
	    	
	        var dsCard = $('<div>', {'class': 'ds-card-container col-md-4 mt-1'})
	        .data({
				'type':dc.type,
				'id':dc.ds_or_c_id,
				'mode':dc.display_mode,
				'geometry_url':dc.geometry_url
			});
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
	
	        dsCardGallery.append(dsCardContent);
	        dsCard.append(dsCardGallery);
	
	        dynamicGallery.append(dsCard);
	    });
	}

	
}

Promise.all([waitMapLoad(), waitDocumentReady()])
    .then(() => {
	
	const debouncedUpdates = debounce(() => { // Uses imported lodash function
	    fetchData();
	    updateAreaMap();
	}, 400);    
	
    const countryDropdown = $('#countryDropdown');
    countryDropdown.select2({
        data: dropdown_data,
        width: 'element', // Use CSS rules
        placeholder: $(this).data('placeholder'),
        closeOnSelect: false,
        allowClear: false,
    }).on('select2:selecting', function (e) {
        if(!!e.params.args.data['ccodes']) { // Region selected: add countries from its ccodes
        	e.preventDefault();
        	let ccodes = Array.from(new Set([...e.params.args.data['ccodes'], ...countryDropdown.select2('data').map(country => country.id)]));
        	countryDropdown.val(ccodes).trigger('change');
        }
    }).on('change', function (e) {
		debouncedUpdates();
    });
    
	$('#clearCountryDropdown').on('click', function() {
        countryDropdown.val(null).trigger('change');
    });
    
	const $checkbox_container = $('<div>', {'class': 'checkbox-container'});
	["Dataset", "Place", "Student"].forEach(function(tab_checkbox) {
		$checkbox_container.append(
			$('<label>', {'class': 'checkbox-label'}).text(tab_checkbox)
			.prepend( $('<input>', {'type': 'checkbox', 'checked': 'checked', name: `${tab_checkbox.toLowerCase()}_checkbox`, 'id': `${tab_checkbox.toLowerCase()}_checkbox`}) ) 
		)
	})
	$('#collections-tab').append($checkbox_container);
			
	[ // description, title, disabled-title, disability test, click-page
		["skip-first", "First page", "(already at first page of results)", "data.current_page == 1", "1"], 
		["skip-previous", "Previous page", "(already at first page of results)", "data.current_page == 1", "data.current_page - 1"], 
		["dropbox", "Select page", "(this is the only page of results)", "data.total_pages == 1", ""], 
		["skip-next", "Next page", "(already reached last page of results)", "data.current_page == data.total_pages", "data.current_page + 1"], 
		["skip-last", "Last page", "(already reached last page of results)", "data.current_page == data.total_pages", "data.total_pages"]
	].forEach(function(control) {
		const $control = control[0] == 'dropbox' ?
			$('<select>', {'title': control[1], 'aria-label': control[1]}) :
			$('<button>', {'id': control[0], 'type': 'button', 'style': `background-image: url(/static/images/sequencer/${control[0]}-btn.svg)`})
		$control
		.data('titles', control.slice(1,3))
		.data('disability', control[3])
		.data('click-page', control[4])
		.on('click change', function(e) {
			page = $(this).is('button') ? $(this).data('page') : $(this).val();
			if ($(this).is('button') || e.type === 'change') fetchData();
		});
		$page_controls.append( $control );	
	});
	$select = $page_controls.find('select');
    
    function fetchData() {
		const classes = $('.checkbox-label input:checked').map(function () {
		    return $(this).closest('label').text().toLowerCase();
		}).get().join(',');
		const sort = ($('#reverseSortCheckbox').prop('checked') ? '-' : '') + $('#sortDropdown').val();
    	const countries = countryDropdown.select2('data').map(country => country.id).join(',');
    	const search = $('#searchInput').val();
    	const url = `/api/gallery/${datacollection}/?page=${page}&classes=${ datacollection=='collections' ? classes : '' }&sort=${sort}&countries=${countries}&q=${search}`;
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
            $select.empty();
		    for (let i = 1; i <= data.total_pages; i++) {
		      const $option = $(`<option value=${i}>page ${i} of ${data.total_pages}</option>`)
		      .attr('selected', i == data.current_page);
		      $select.append($option);
		    }
		    $page_controls.find('button, select').each(function() {
				const disabled = eval($(this).data('disability'));
				$(this)
				.data('page', eval($(this).data('click-page')))
				.attr('disabled', disabled)
				.attr('title', $(this).data('titles')[disabled ? 1 : 0])
				.attr('aria-label', $(this).data('titles')[disabled ? 1 : 0]);
			});	
        })
        .catch(error => {
            console.error('Fetch error:', error);
        });
    }
    
    debouncedUpdates(); // Fetch and build initial gallery; set map filter
    
    function resetMap() {
		mappy.flyTo({
 			center: mapParameters.center,
 			zoom: mapParameters.zoom,
 	        speed: .5,
 	    });
	}
    
    function updateAreaMap() {
    	const countries = countryDropdown.select2('data').map(country => country.id);
        countryCache.filter(countries).then(filteredCountries => {
            mappy.getSource('places').setData(filteredCountries);

            try {
                mappy.fitBounds(bbox(filteredCountries), {
                    padding: 30,
                    maxZoom: 7,
                    duration: 1000,
                });
            } catch {
                resetMap();
            }
        });
    }
    
    $('a[data-bs-toggle="tab"]').on('shown.bs.tab', function () {
		datacollection = $(this).attr('href').substring(1);
		fetchData();
	});
    
    $('.checkbox-container').on('mouseup', function(e) {
		let checkbox_label = $(e.target).closest('.checkbox-label');
		let already_active = $(e.target).closest('.nav-link').hasClass('active');
		if (checkbox_label.length) {
			let checkbox = checkbox_label.find('input');
			checkbox.prop('checked', !checkbox.prop('checked')); // Repair checkbox behaviour suppressed by <a> wrapper
			if (already_active) fetchData(); // Otherwise triggered by Bootstrap tab
		}
    });
    
    $('#sortDropdown, #reverseSortCheckbox, #searchInput').on('change', function () {
        fetchData();
    });
    
    $('body').on('mouseenter', '.ds-card-container', (e) => {
		fetchDataForHorse($(e.target).closest('.ds-card-container'), mappy);
	}).on('mouseleave', '.ds-card-container', () => {
		mappy.getSource('featured-data-source').setData(nullCollection);
		resetMap();
	});
	
	$('#searchInput').on('input', function() {fetchData();});
	$('#clearSearchButton').on('click', function() {
        $('#searchInput').val('');
        fetchData();
    });
    
    // Force country filter to track width of search filter
    const resizeObserver = new ResizeObserver(entries => {
	    $('.select2-container').css('width', entries[0].target.offsetWidth);
	});
	resizeObserver.observe($('#searchInput')[0]);
    
});