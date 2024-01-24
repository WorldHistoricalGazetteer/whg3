// /whg/webpack/home.js

import { geomsGeoJSON } from './utilities';
import '../css/home.css';
import featuredDataLayers from './featuredDataLayerStyles';
import { fetchDataForHorse } from './localGeometryStorage';

let mappy = new whg_maplibre.Map({
	navigationControl: false,
	maxZoom: 10
});

var timer; // Controls the carousels

mappy.on('load', function() {
	console.log('Map loaded.');

	const style = mappy.getStyle();
	style.layers.forEach(layer => { // Hide map labels
		if (layer.id.includes('label')) {
			mappy.setLayoutProperty(layer.id, 'visibility', 'none');
		}
	});
	
	mappy.newSource('featured-data-source');  // Add empty source
	
	featuredDataLayers.forEach(layer => {
		mappy.addLayer(layer);
	});
		
	$(document).ready(function() {

		galleries.forEach(gallery => {
			const [title, url] = gallery;
			const type = title.toLowerCase();
			const carouselContainer = $('<div class="carousel-container p-1 home-carousel"></div>');
			const border = $('<div class="border p-1 h-100"></div>');
			const heading = $(`<h6 class="p-1 strong">${ title }</h6>`);
			if (type == 'datasets') {
				heading.addClass("ds-header")
			} else {
				heading.addClass("coll-header")
			}
			const galleryLink = url == null ? '' : `<span class="float-end small"><a class="linkylite" href="${ url }">view all</a></span>`;
			const carousel = $(`<div id="${type.toLowerCase()}Carousel" class="carousel slide carousel-fade h-100"></div>`);
			const carouselInner = $('<div class="carousel-inner"></div>');
			const prevButton = $(`<button class="carousel-control-prev" type="button" data-bs-target="#${type}Carousel" data-bs-slide="prev">
		                            <span class="carousel-control-prev-icon" aria-hidden="true"></span>
		                            <span class="visually-hidden">Previous</span>
		                        </button>`);
			const nextButton = $(`<button class="carousel-control-next" type="button" data-bs-target="#${type}Carousel" data-bs-slide="next">
		                            <span class="carousel-control-next-icon" aria-hidden="true"></span>
		                            <span class="visually-hidden">Next</span>
		                        </button>`);
			heading.append(galleryLink);
			border.append(heading);
			carousel.append(carouselInner);
			carousel.append(prevButton);
			carousel.append(nextButton);
			border.append(carousel);
			carouselContainer.append(border);
			$('#carousel-outer-container').append(carouselContainer);
		});

		carousel_metadata.forEach(datacollection => {
			const target = $('#' + datacollection.type + 'sCarousel .carousel-inner');
			const carouselItem = $(`<div class="carousel-item${ target.children('.carousel-item').length == 0 ? ' active' : '' } p-2"></div>`);
			const description = datacollection.description.length > 100 ? datacollection.description.substring(0, 100) + '...' : datacollection.description;
			if (datacollection.image_file) {
				const imageElement = $(`<img src="${datacollection.image_file}" class="carousel-image">`);
				carouselItem.append(imageElement);
			}
			carouselItem.append(`
		        <h6>
		            <a href="${datacollection.url}">${datacollection.title}</a>
		        </h6>
		        <p>${description}</p>
		    `)
				.data({
					id: datacollection.ds_or_c_id,
					type: datacollection.type,
					mode: datacollection.display_mode,
					geometry_url: datacollection.geometry_url
				});
			target.append(carouselItem);
		});
		fetchDataForHorse( $('.carousel-item:first'), mappy );

		var carousels = $('.carousel');
		let delay = 10000;
		let mouseover = false;
		if (startCarousels) carousels.first().carousel({
			interval: delay,
			ride: 'carousel',
			keyboard: false, // Ignore keyboard
		}).on('slide.bs.carousel', function() {
			if (!mouseover) {
				timer = setTimeout(function() {
					carousels.eq(1).carousel('next');
				}, delay / 2);
			}
		});
		carousels.eq(1).carousel({
			keyboard: false, // Ignore keyboard
		});

		carousels.on('slid.bs.carousel', function() {
			$('.carousel-container .border').removeClass('highlight-carousel');
		    fetchDataForHorse( $(this).find('.carousel-item.active'), mappy );
		});
		$('.carousel-container').on('mouseenter', function() {
			if (startCarousels) carousels.first().carousel('pause');
			clearTimeout(timer);
			mouseover = true;
		}).on('mouseleave', function() {
			if (startCarousels) carousels.first().carousel('cycle');
			mouseover = false;
		})
		// Cycling restarts on button click unless carousel is paused, even though mouse has not left container
		$('.carousel-control-next').on('click', function() {
			if (startCarousels) carousels.first().carousel('pause');
			$($(this).data('bs-target')).carousel('next');
		});
		$('.carousel-control-prev').on('click', function() {
			if (startCarousels) carousels.first().carousel('pause');
			$($(this).data('bs-target')).carousel('prev');
		});

	})

});


let idToArea = {}
let area_list = []
let area_objs = []

$(function() {
	// always clear last_results & last_query
	localStorage.removeItem('last_results')
	localStorage.removeItem('last_query')

	// listen for search action
	// TODO: handle Enter key also
	$("#a_search").click(function() {
		initiateSearchHome();
	});

	$("#search_map input").on('keypress', function(event) {
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

	$.get("/api/area_list", function(data) {
		//console.log('initial areas for list',data)
		for (var i = 0; i < data.length; i++) {
			area_objs.push(data[i])
			area_list.push(data[i]['title'])
		}
	})
	$("#input_area").autocomplete({
		source: area_list,
		minLength: 2,
		select: function(event, ui) {
			// build boundsobj, insert as hidden input val()
			let label = ui.item.label
			let obj = area_objs.find(o => o.title == label)
			let areaid = obj.id
			let boundsobj = '{"type":["' + obj.type + '"],"id":["' + areaid + '"]}'
			$("#boundsobj").val(boundsobj)
			console.log("boundsobj for view ", boundsobj);

			// fetch and render selected area
			render_area(areaid)
		}
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
			url: '/api/area/' + areaid
		}).done(function(data) {
			console.log('render_area() data', data)
			let geom = {
				"type": "FeatureCollecton",
				"features": []
			}
			geom['features'].push(data.geojson)
			console.log('render_area() geom', geom)

			// clear existing
			if (typeof arealayer !== 'undefined') {
				arealayer.removeFrom(mappy)
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
		})
	}
	// call views.search_new() with parameters
	// search_new() will pass these to search_new.html
	function initiateSearchHome() {
		const query = $('#search_map input').val();
		const filters = gatherOptions();
		localStorage.setItem('last_query', query)

		$.get("/search/index", filters, function(data) {
			window.searchres = data['suggestions']
			window.session = data['session']

			console.log(filters);

			// store locally
			let results = geomsGeoJSON(searchres); // Convert to GeoJSON
			results.query = query;
			localStorage.setItem('checkedboxes', '[]');
			localStorage.setItem('last_results', JSON.stringify(results));

			console.log(searchres)
			// if results, deliver to search_new.html
			if (searchres.length > 0) {
				window.location.href = "/search";
			} else {
				alert('no results for "' + query + '", sorry')
			}
		});
	}

	// toggle all fclass checkboxes
	$("#check_toggle").click(function(e) {
		e.preventDefault()
		var state = $("#check_toggle").text()
		if (state == 'check all') {
			$("input:checkbox").prop('checked', true);
			$("#check_toggle").text('clear all');
		} else if (state == 'clear all') {
			$("input:checkbox").prop('checked', false);
			$("#check_toggle").text('check all');
		}
	})

	// get option values
	function gatherOptions() {
		// test
		//{#options = {"fclasses":"P"}#}
		// gather and return option values from the UI
		let fclasses = [];
		// the whg index, for dev or prod according to local_settings
		var eswhg = "{{ es_whg|escapejs }}";
		$('#adv_checkboxes input:checked').each(function() {
			fclasses.push($(this).val());
		});
		console.log('checked', fclasses)
		let options = {
			"qstr": $('#search_map input').val(),
			"idx": eswhg,
			// "idx": "whg",
			"fclasses": fclasses.join(','),
			"start": $("#input_start").val(),
			"end": $("#input_end").val(),
			"bounds": $("#boundsobj").val()
		}
		return options;
	}

	$("[rel='tooltip']").tooltip();
	// modal for images
	$('.pop').on('click', function() {
		let url = $(this).find('img').attr('src')
		let txt = $(this).find('img').attr('alt')
		let re = /(.png|.jpg|.jpeg|.gif|.tif)/g
		let ext = url.match(re)[0]
		url = url.replace(ext, '_full' + ext)
		$("#header_text").html(txt)
		$('.imagepreview').attr('src', url);
		$('#image_modal').modal('show');
	});

})

let homeModal = document.getElementById('homeModal')
homeModal.addEventListener('show.bs.modal', function(event) {
	// Button that triggered the modal
	var button = event.relatedTarget
	// Extract info from data-bs-* attributes
	var title = button.getAttribute('data-bs-title')
	var page = button.getAttribute('data-bs-page')
	console.log('button_id', page)

	// update the modal title
	var modalTitle = homeModal.querySelector('.modal-title')
	modalTitle.textContent = title

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
			console.log('status, error', status, error)
		}
	});
})