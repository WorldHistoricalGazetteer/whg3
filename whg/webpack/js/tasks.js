// /whg/webpack/tasks.js

import { geomsGeoJSON } from './utilities';

import '../css/tasks.css';

let mapParameters = { 
	maxZoom: 10,
	temporalControl: {
        fromValue: 1550,
        toValue: 1720,
        minValue: -2000,
        maxValue: 2100,
        open: false,
        includeUndated: true, // null | false | true - 'false/true' determine state of select box input; 'null' excludes the button altogether
        epochs: null,
        automate: null,
    },
}
let whg_map = new whg_maplibre.Map(mapParameters);

function waitMapLoad() {
    return new Promise((resolve) => {
        whg_map.on('load', () => {
            console.log('Map loaded.');
			
			whg_map
			.newSource('places') // Add empty source
			.newLayerset('places', null, 'plain');
            
            resolve();
        });
    });
}

function waitDocumentReady() {
    return new Promise((resolve) => {
        $(document).ready(() => resolve());
    });
}

Promise.all([waitMapLoad(), waitDocumentReady()])
    .then(() => {

		let msgs = ["{{ msg_wdlocal.type }}", "{{ msg_whg.type }}"]
		console.log('msgs', msgs)
		if ("{{ msg_wdlocal.type }}" == 'done' && '{{ ds.ds_status }}' != 'updated') {
			$("#r_wdlocal").attr('disabled', true)
			$("#r_whg").prop('checked', 'true')
		}
		let found = msgs.slice(0, 2).some(r => ['none', 'unreviewed', 'inprogress'].includes(r))
	
		if (msgs.slice(0, 2).includes("done") && !found) {
			$("#addtask_lower").addClass("hidden")
		}
	
		// set default 
		$("#r_keep_wd").attr('checked', true)
	
		$("#cancel_taskadd").click(function(e) {
			e.preventDefault();
			window.location.href = "{% url 'datasets:ds_reconcile' ds.id %}"
		})

	  // hide REVIEW OPTIONS div if "WHG accession" is selected
		$("input[name='recon']").change(function() {
			if (this.value === 'idx') {
				$("#review_options").hide();
			} else if (this.value === 'wdlocal') {
				$("#review_options").show();
			}
		});

		// modal buttons
		$("#btn_done").on('click', function() {
			location.reload();
		})
		$("#btn_cancel").on('click', function() {
			location.reload();
		})

		// window.limiter = []
		// clear data limiter dropdown choice if other is used
		$("#select_colls").change(function(event) {
			event.preventDefault()
			$("#collection_id").val($(this).val())
			console.log('recon to collection', $(this).val())
		});

		// clear dropdown choice if other is used & render geometry
		$("#select_region").change(function() {
			$("#select_userarea option[value=0]").prop('selected', true)
			if ($(this).val() == 0) {
				reset_map()
			} else {
				render_area($(this).val(), 'region')
			}
		});
		
    	var selectUserArea = $("#select_userarea");
		selectUserArea
		.change(function() {
			$("#select_region option[value=0]").prop('selected', true)
	        const selectedValue = $(this).val();
	        const noneSelected = selectedValue == 0;
			if (noneSelected) {
				reset_map();
			} else {
				render_area(selectedValue, 'area');				
			}
			$(this).next('span')
			.toggleClass('hidden', noneSelected)
			.find('a')
            .attr('href', function(_, currentUrl) {
                return currentUrl.replace(/\/areas\/\d+\/update/, `/areas/${selectedValue}/update`);
            });
		})
		.val(selectUserArea.data('initial-select'))
		.trigger('change');
		
		// Add event listener to each radio button
		let radios = $('.r_recon');
		let selectColls = $('#select_colls');
		radios.each(function() {
		  	$(this).change(function() {
				selectColls.toggle(this.value === 'collection');
		  	});
		});		
 
    })
    .catch(error => console.error("An error occurred:", error));

function renderMap(featureCollection, tab) {
	if (featureCollection.features.length == 0) {
		console.log('no features in renderMap() call')
	} else {
		
		whg_map.getSource('places').setData(featureCollection);
		whg_map.setFeatureState({ source: 'places', id: 0 }, { highlight: true });
	}
	whg_map.fitBounds(bbox(featureCollection), {
        padding: 30,
        duration: 1000,
    });
}

// area-related
function render_area(aid) {
	$.ajax({
		url: '/api/area/' + aid
	}).done(function(data) {
		data['geom'] = data.geojson;
		delete data.geojson;
		let featureCollection = geomsGeoJSON([data])
		console.log('render_area()', data, featureCollection)
		renderMap(featureCollection, 'area')
		$("#area_name").html(data.title).show()
	})
}

function reset_map() {
	$("#area_name").html('Global');
	whg_map
	.clearSource('places')
	.reset();
}
