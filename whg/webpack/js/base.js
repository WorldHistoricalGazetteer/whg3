// base.js

import { Spinner } from 'spin.js';
import '../../../static/js/aliases.js';
import 'bootstrap/dist/css/bootstrap.min.css';
import 'jquery-ui/dist/themes/base/jquery-ui.min.css';
import '../css/base.css';
import '@fortawesome/fontawesome-free/css/all.min.css';
import '../../static/css/styles.css';
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
		cdnUrl: 'https://code.jquery.com/jquery-3.6.3.min.js',
		localUrl: '/node_modules/jquery/dist/jquery.min.js',
		position: 'head'
	},
	{
		cdnUrl: 'https://cdnjs.cloudflare.com/ajax/libs/bootstrap/5.2.3/js/bootstrap.bundle.min.js',
		localUrl: '/node_modules/bootstrap/dist/js/bootstrap.bundle.min.js',
		position: 'body'
	},
	{
		cdnUrl: 'https://code.jquery.com/ui/1.13.2/jquery-ui.min.js',
		localUrl: '/node_modules/jquery-ui/dist/jquery-ui.min.js',
		position: 'head'
	},
	{
		cdnUrl: 'https://cdnjs.cloudflare.com/ajax/libs/clipboard.js/2.0.11/clipboard.min.js',
		localUrl: '/node_modules/clipboard/dist/clipboard.min.js',
		position: 'head'
	},
];

function loadResource(element) {
	return new Promise(function(resolve, reject) {
		var resource = document.createElement('script');

		resource.src = element.cdnUrl;
		resource.type = 'text/javascript';

		if (element.integrity) resource.integrity = element.integrity;
		if (element.crossorigin) resource.crossorigin = element.crossorigin;
		
		document[element.position].appendChild(resource);

		resource.onload = function() {
			console.log(`Loaded CDN resource ${element.cdnUrl}`);
			resolve();
		}
		resource.onerror = function() {
			console.error(`Failed to load CDN resource (${element.cdnUrl}), falling back to local: ${element.localUrl}`);

			resource.onload = resource.onerror = null; // Clear previous event handlers
			resource.src = element.localUrl;
		
			document[element.position].appendChild(resource);

			resource.onload = function() {
		        console.log(`Loaded local resource ${element.localUrl}`);
		        resolve();
		    };
			resource.onerror = function() {
				reject(new Error(`Also failed to load local resource (${element.localUrl}).`));
			};
		};
	});
}

Promise.all(CDN_fallbacks.map(loadResource))
	.then(function() {
		
		console.log('Executing deferred scripts.');
		executeDeferredScripts();
		
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