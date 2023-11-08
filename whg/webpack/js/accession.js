// /whg/webpack/js/accession.js

import { mappy, initialiseMap, addReviewListeners } from './review-common';

function waitMapLoad() {
    return new Promise((resolve) => {
        mappy.on('load', () => {
			initialiseMap();
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
		
		placeid = $('script').filter(function() { // TODO: Redundant code?
			return this.id.match("placeid")
		}).text();
		
		if (test == "on") {
			$("#review_nav").css("background-color", "lightsalmon");
			$("input:radio").attr("disabled", "disabled");
			$("#btn_save").hide();
			$("#defer_link").hide();
		}
	
		var dspop = $(".pop-dataset").popover({
			trigger: 'focus',
			placement: 'right',
			html: true
		}).on('show.bs.popover', function() {
			$.ajax({
				url: '/api/datasets/',
				data: {
					label: $(this).data('label')
				},
				dataType: "JSON",
				async: false,
				success: function(data) {
					let ds = data.results[0]
					//console.log('ds',ds)
					let html = '<p class="thin"><b>Title</b>: ' + ds.title + '</p>'
					html += '<p class="thin"><b>Description</b>: ' + ds.description + '</p>'
					html += '<p class="thin"><b>WHG Owner</b>: ' + ds.owner + '</p>'
					html += '<p class="thin"><b>Creator</b>: ' + ds.creator + '</p>'
					dspop.attr('data-content', html);
				}
			});
		});
		
		addReviewListeners();
		
	})
    .catch(error => console.error("An error occurred:", error));
