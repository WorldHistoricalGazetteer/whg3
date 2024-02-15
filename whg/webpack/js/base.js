// base.js

import { Spinner } from 'spin.js';
import '../../../static/js/aliases.js'; // /static/js/aliases.js
import '../css/base.css';
import '../../static/css/styles.css'; // /whg/static/css/styles.css
import 'spin.js/spin.css';
	
if ('fonts' in document) {
	const fontFamilies = ['Raleway', 'Archivo Black'];

	const fontPromises = fontFamilies.flatMap(font => [
		document.fonts.load(`normal 1em "${font}"`),
		document.fonts.load(`bold 1em "${font}"`),
		document.fonts.load(`italic 1em "${font}"`),
		document.fonts.load(`italic bold 1em "${font}"`),
	]);

	Promise.all(fontPromises).then(_ => {
		document.documentElement.classList.add('fonts-loaded');
	});
}

var CDN_fallbacks = [
	{
		cdnUrl: 'https://cdnjs.cloudflare.com/ajax/libs/bootstrap/5.2.3/css/bootstrap.min.css',
		localUrl: 'bootstrap.min.css',
		position: 'head'
	},
	{
		cdnUrl: 'https://cdnjs.cloudflare.com/ajax/libs/jqueryui/1.13.2/themes/base/jquery-ui.min.css',
		localUrl: 'jquery-ui.min.css',
		position: 'head'
	},
	{
		cdnUrl: 'https://cdnjs.cloudflare.com/ajax/libs/clipboard.js/2.0.11/clipboard.min.js',
		localUrl: 'clipboard.min.js',
		position: 'head'
	},
	{
		cdnUrl: 'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css',
		localUrl: 'all.min.css',
		position: 'head'
	},
	{
		cdnUrl: 'https://cdnjs.cloudflare.com/ajax/libs/d3/4.13.0/d3.min.js',
		localUrl: 'd3.min.js',
		position: 'head'
	},
];

var jquery_fallbacks = [
	{
		cdnUrl: 'https://code.jquery.com/jquery-3.6.3.min.js',
		localUrl: 'jquery.min.js',
		position: 'head'
	},	
]

var jquery_dependent_fallbacks = [
	{
		cdnUrl: 'https://cdnjs.cloudflare.com/ajax/libs/bootstrap/5.2.3/js/bootstrap.bundle.min.js',
		localUrl: 'bootstrap.bundle.min.js',
		position: 'body'
	},
	{
		cdnUrl: 'https://code.jquery.com/ui/1.13.2/jquery-ui.min.js',
		localUrl: 'jquery-ui.min.js',
		position: 'head'
	},
	{
		cdnUrl: 'https://cdnjs.cloudflare.com/ajax/libs/typeahead.js/0.11.1/typeahead.bundle.min.js', // Includes both typeahead and bloodhound
		localUrl: 'typeahead.bundle.min.js',
		position: 'head'
	},
	
]

var maplibre_fallbacks = [
	{
		cdnUrl: 'https://unpkg.com/maplibre-gl@latest/dist/maplibre-gl.js',
		localUrl: 'maplibre-gl.js',
		position: 'head',
	},
	{
		cdnUrl: 'https://unpkg.com/maplibre-gl@latest/dist/maplibre-gl.css',
		localUrl: 'maplibre-gl.css',
		position: 'head'
	},
	{
		cdnUrl: 'https://cdnjs.cloudflare.com/ajax/libs/Turf.js/6.5.0/turf.min.js',
		localUrl: 'turf.min.js',
		position: 'head'
	},
];

window.select2_CDN_fallbacks = [
	{
		cdnUrl: 'https://cdnjs.cloudflare.com/ajax/libs/select2/4.0.13/js/select2.full.min.js',
		localUrl: 'select2.full.js',
		position: 'head',
	},
	{
		cdnUrl: 'https://cdnjs.cloudflare.com/ajax/libs/select2/4.0.13/css/select2.min.css',
		localUrl: 'select2.css',
		position: 'head'
	},
];

window.datatables_CDN_fallbacks = [
	{
		cdnUrl: 'https://cdn.datatables.net/v/dt/dt-1.10.24/b-1.7.0/b-colvis-1.7.0/b-html5-1.7.0/cr-1.5.3/fh-3.1.8/sc-2.0.3/sp-1.2.2/sl-1.3.3/datatables.min.js',
		localUrl: 'datatables.min.js',
		position: 'head',
	},
	{
		cdnUrl: 'https://cdn.datatables.net/v/dt/dt-1.10.24/b-1.7.0/b-colvis-1.7.0/b-html5-1.7.0/cr-1.5.3/fh-3.1.8/sc-2.0.3/sp-1.2.2/sl-1.3.3/datatables.min.css',
		localUrl: 'datatables.min.css',
		position: 'head'
	},
];

window.loadResource = function(element) {
	return new Promise(function(resolve, reject) {
		var resource;
		const isCSS = element.cdnUrl.endsWith('.css');
		const parentElement = document[element.position];
		
		if (isCSS) {
			resource = document.createElement('link');
			resource.type = 'text/css';
			resource.rel = 'stylesheet';
		} else {
			resource = document.createElement('script');
			resource.type = 'text/javascript';
		}

		resource[isCSS ? 'href' : 'src'] = element.cdnUrl;

		if (element.integrity) resource.integrity = element.integrity;
		if (element.crossorigin) resource.crossorigin = element.crossorigin;
			
		var localResource = resource.cloneNode();
		localResource[isCSS ? 'href' : 'src'] = `/CDNfallbacks/${element.localUrl}`;

		resource.onload = function() {
			// console.log(`Loaded CDN resource ${element.cdnUrl}`);
			resolve();
		};

		resource.onerror = function() {			
			console.log(`Failed to load CDN resource (${element.cdnUrl}), falling back to local: ${element.localUrl}`);
			
			localResource.onload = function() {
				console.log(`Loaded LOCAL resource ${element.localUrl}`);
				resolve();
			};
			localResource.onerror = function() {
				console.log(`FAILED to load local resource ${element.localUrl}`);
				resolve();
			};
			
			parentElement.insertBefore(localResource, resource);
			parentElement.removeChild(resource);

		};

		parentElement.appendChild(resource);
	});
};

if (typeof loadMaplibre !== 'undefined') {
	CDN_fallbacks = [...CDN_fallbacks, ...maplibre_fallbacks];
}

Promise.all([
    Promise.all(CDN_fallbacks.map(loadResource)),
	Promise.all(jquery_fallbacks.map(loadResource)) // Ensure that JQuery is loaded before proceeding with its dependents
		.then(function() {
			return Promise.all(jquery_dependent_fallbacks.map(loadResource));
		})
	])
	.then(function() {
		
		document.querySelector('body').style.opacity = 1;
		
		if (typeof scripts !== 'undefined') {
			console.log('Executing deferred scripts.');
			executeDeferredScripts();
		}		
		
		if (typeof loadMaplibre !== 'undefined') {
			window.bbox = turf.bbox;
			window.buffer = turf.buffer;
			window.convex = turf.convex;
			window.flatten = turf.flatten;
			window.dissolve = turf.dissolve;
			window.combine = turf.combine;
			window.midpoint = turf.midpoint
			window.centroid = turf.centroid
			window.getType = turf.getType
			window.area = turf.area
			window.distance = turf.distance
			window.lineString = turf.lineString
			window.bezierSpline = turf.bezierSpline
		}
		
		window.Spinner = Spinner;
		
		var language = window.navigator.language.substr(0, 2);

		// Hide/show links based on the URL
		var url = window.location.pathname;
		if (url !== '/') {
			$("#links_home").addClass('d-none');
			$("#links_other").removeClass('d-none');
		}

		// Highlight active links based on the URL
		var abouts = ['/about/', '/system/', '/licensing/', '/credits/'];
		var clicked = window.location.pathname;

		if ($.inArray(clicked, abouts) > -1) {
			console.log('in abouts');
			$("#aboutDropdown").addClass('navactive');
		} else {
			$("[href='" + clicked + "']").addClass('navactive');
		}

		// Feedback click event
		$(".feedback").click(function() {
			console.log(clicked);
			var url = "/contact?from=" + encodeURIComponent(clicked);
			window.location.href = url;
		});
	})
	.catch(function(error) {
		console.error('Error loading resources:', error);
	});