// /whg/webpack/home.js

import '../css/home.css';
import { initialiseCarousels } from './carousels';

let mappy = new whg_maplibre.Map({
	navigationControl: false,
	maxZoom: 10,
});

//let idToArea = {};
let area_list = [];
let area_objs = [];

function waitMapLoad() {
	return new Promise((resolve) => {
		mappy.on('load', () => {
			console.log('Map loaded.');

			const style = mappy.getStyle();
			style.layers.forEach(layer => { // Hide map labels
				if (layer.id.includes('label')) {
					mappy.setLayoutProperty(layer.id, 'visibility', 'none');
				}
			});
			
			$('.maplibregl-control-container')
			.wrap('<div id="controlWrapper"></div>')
			.after($('#carousel-outer-container'));

			resolve();
		});
	});
}

function waitDocumentReady() {
	return new Promise((resolve) => {
		$(document).ready(() => resolve());
	});
}

Promise.all([
	waitMapLoad(),
	waitDocumentReady()
]).then(() => {
	
	initialiseCarousels(galleries, carouselMetadata, startCarousels, mappy);

	// always clear last_search (if set)
	localStorage.removeItem('last_search');

	// listen for search action
	$('#initiate_search').click(function() {
		initiateSearchHome();
	});

	$('#search_input').on('keyup', function(event) {
		if (event.which == 13) { // 13 is the 'Enter' key code
			event.preventDefault();
			initiateSearchHome(); // Call the initiateSearch function when 'Enter' is pressed
		}
	});

	$('#a_advanced').on('click', function(e) {
		e.preventDefault();
		clearTimeout(timer); // Stop the carousels
		if (startCarousels) $('.carousel').first().carousel('pause');
		$('#advanced_search').slideToggle(300); // This toggles the visibility of the advanced search div
	});

	$.get('/api/area_list', function(data) {
		//console.log('initial areas for list',data)
		for (var i = 0; i < data.length; i++) {
			area_objs.push(data[i]);
			area_list.push(data[i]['title']);
		}
	});
	$('#input_area').autocomplete({
		source: area_list,
		minLength: 2,
		select: function(event, ui) {
			// build boundsobj, insert as hidden input val()
			let label = ui.item.label;
			let obj = area_objs.find(o => o.title == label);
			let areaid = obj.id;
			let boundsobj = '{"type":["' + obj.type + '"],"id":["' + areaid + '"]}';
			$('#boundsobj').val(boundsobj);
			console.log('boundsobj for view ', boundsobj);

			// fetch and render selected area
			render_area(areaid);
		},
	});
	/*  {#$("#input_area").on('keyup', function(e){#}
	  {#  // resets stuff#}
	  {#  if($('#input_area').val().length < 3) {#}
	  {#    $("#boundsobj").val('')#}
	  {#    if(typeof arealayer !== 'undefined'){arealayer.removeFrom(mappy)}#}
	  {#    mappy.setView([38, 10], 2.4)#}
	  {#  }#}
	  {# })#}*/
	let render_area = function(areaid) {
		$.ajax({
			url: '/api/area/' + areaid,
		}).done(function(data) {
			console.log('render_area() data', data);
			let geom = {
				'type': 'FeatureCollecton',
				'features': [],
			};
			geom['features'].push(data.geojson);
			console.log('render_area() geom', geom);

			// clear existing
			if (typeof arealayer !== 'undefined') {
				arealayer.removeFrom(mappy);
			}

			// TODO: NOT YET render new
			/*    {#arealayer = L.geoJSON(geom, {#}
			    {#  onEachFeature: function(feature,layer) {#}
			    {#  f=feature; l=layer;#}
			    {#  console.log('render_area() f,l',f,l)#}
			    {#  l.setStyle({"color":"orange","weight":2,"fillOpacity":0})#}
			    {#  idToArea[areaid] = l#}
			    {#  popupOptions = {maxWidth: 200};#}
			    {#  l.bindPopup(data.title, popupOptions);#}
			    {#  }#}
			    {# }).addTo(mappy)#}
			    {#mappy.fitBounds(arealayer.getBounds())#}*/
		});
	};
	
	// call views.search_new() with parameters
	// search_new() will pass these to search_new.html
	function initiateSearchHome() {
		const filters = {
			'qstr': $('#search_input').val(),
			'mode': 'exactly',
			'idx': eswhg, // hard-coded in html template
			'fclasses': '',
			'start': null,
			'end': null,
			'bounds': null,
		};

		// AJAX POST request to SearchView() with the options (includes qstr)
		$.ajax({
			type: 'POST',
			url: '/search/index/',
			data: JSON.stringify(filters),
			contentType: 'application/json',
			headers: {
				'X-CSRFToken': document.querySelector(
					'[name=csrfmiddlewaretoken]').value,
			}, // Include CSRF token in headers for Django POST requests
			success: function(data) {
				console.log('...search completed.', data);
				localStorage.setItem('last_search', JSON.stringify(data)); // Includes both `.parameters` and `.suggestions` objects
				if (data.suggestions.length > 0) { // if results, load and render on Search page
					window.location.href = '/search';
				} else {
					alert('no results for "' + filters.qstr + '", sorry');
				}
			},
			error: function(error) {
				console.error('Error:', error);
			},
		});
	}

	// toggle all fclass checkboxes
	$('#check_toggle').click(function(e) {
		e.preventDefault();
		var state = $('#check_toggle').text();
		if (state == 'check all') {
			$('input:checkbox').prop('checked', true);
			$('#check_toggle').text('clear all');
		} else if (state == 'clear all') {
			$('input:checkbox').prop('checked', false);
			$('#check_toggle').text('check all');
		}
	});

	$('[rel=\'tooltip\']').tooltip();
	// modal for images
	$('.pop').on('click', function() {
		let url = $(this).find('img').attr('src');
		let txt = $(this).find('img').attr('alt');
		let re = /(.png|.jpg|.jpeg|.gif|.tif)/g;
		let ext = url.match(re)[0];
		url = url.replace(ext, '_full' + ext);
		$('#header_text').html(txt);
		$('.imagepreview').attr('src', url);
		$('#image_modal').modal('show');
	});

	// announcements (w/fade)
	let currentIndex = 0;
	const announcements = $('#announcement-container .announcement');
	const totalAnnouncements = announcements.length;

	function rotateAnnouncements() {
		const currentAnnouncement = $(announcements[currentIndex]);
		const nextIndex = (currentIndex + 1) % totalAnnouncements;
		const nextAnnouncement = $(announcements[nextIndex]);

		// Fade out the current announcement and fade in the next
		currentAnnouncement.fadeOut(500, function() {
			nextAnnouncement.fadeIn(500);
		});

		currentIndex = nextIndex;
	}

	// Start rotating announcements every 3 seconds, plus the fade time to ensure one fades out before the next fades in
	setInterval(rotateAnnouncements, 5000); // Adjust time as needed


	// let currentIndex = 0;
	// const announcements = document.querySelectorAll(
	//     '#announcement-container .announcement');
	// const totalAnnouncements = announcements.length;
	//
	// function rotateAnnouncements() {
	// 	console.log('rotateAnnouncements()');
	//   // Hide the current announcement
	//   announcements[currentIndex].style.display = 'none';
	//
	//   // Calculate the index of the next announcement to show
	//   currentIndex = (currentIndex + 1) % totalAnnouncements;
	//
	//   // Show the next announcement
	//   announcements[currentIndex].style.display = 'block';
	// }
	//
	// // Start rotating announcements every 5 seconds
	// setInterval(rotateAnnouncements, 5000);	//
	// console.log("DOMContentLoaded event listener has been added");


	let homeModal = document.getElementById('homeModal');
	homeModal.addEventListener('show.bs.modal', function(event) {
		// Button that triggered the modal
		var button = event.relatedTarget;
		// Extract info from data-bs-* attributes
		var title = button.getAttribute('data-bs-title');
		var page = button.getAttribute('data-bs-page');
		console.log('button_id', page);

		// update the modal title
		var modalTitle = homeModal.querySelector('.modal-title');
		modalTitle.textContent = title;

		// get modal body as django template
		$.ajax({
			url: homeModalURL, // Passed as a variable in Django template
			data: {
				'page': page,
			},
			type: 'POST',
			success: function(response) {
				$('.modal-body').html(response);
			},
			error: function(xhr, status, error) {
				console.log('status, error', status, error);
			},
		});
	});

});