// /whg/webpack/js/review.js

import { mappy, layersets, initialiseMap, addReviewListeners } from './review-common';
import './notes.js';

import '../css/review.css';


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

function toggleGeonamesReview() {
	$('#geonames_review').toggle();
}

Promise.all([waitMapLoad(), waitDocumentReady()])
    .then(() => {

    if ($('.wdlocal').length > 0) {
		// hide geonames (gn) initially if any wdlocal records
        $('.gn').hide();
        // $('#toggle_geonames_review').show();
        $('.show-link').show();
    } else {
		// show geonames (gn) initially if no wdlocal records
        $('.gn').show();
        // $('#toggle_geonames_review').hide();
        $('.show-link').hide();
    }

    $('#toggle_geonames_review').on('click', function(e) {
        e.preventDefault(); // prevent the default action

        // toggle visibility of .auth-match and adjacent .matchbar elements associated with 'gn'
        $('.auth-match').each(function() {
            if ($(this).find('a[data-auth="gn"]').length > 0) {
                $(this).prev('.matchbar').toggle();
                $(this).toggle();
            }
        });
        
        // toggle visibility of geonames map markers
        if (!!layersets['geonames']) layersets['geonames'].toggleVisibility();

        // change the text of the link
        $(this).text(function(i, text){
            return text === "Show GeoNames hits" ? "Hide GeoNames hits" : "Show GeoNames hits";
        })
    });

	console.log(`already: ${ already }`)
	if (already !=='') {
		alert('last record was saved by someone else, this is the next')
	}

	if (page_variant == 'accession') {
	
		let placeid = $('script').filter(function() { // TODO: Redundant code?
			return this.id.match("placeid")
		}).text();
		
		if (test == "on") {
			$("#review_nav").css("background-color", "lightsalmon");
			$("input:radio").attr("disabled", "disabled");
			$("#btn_save").hide();
			$("#defer_link").hide();
		}

		$(".pop-dataset").popover({
		    trigger: 'hover',
		    placement: 'right',
		    html: true,
		    content: function () {
		        var label = $(this).data('label');
		        var details = datasetDetails[label];
		        return `
		            <p class="thin"><b>Title</b>: ${details['title']}</p>
		            <p class="thin"><b>Description</b>: ${details['description']}</p>
		            <p class="thin"><b>WHG Owner</b>: ${details['owner']}</p>
		            <p class="thin"><b>Creator</b>: ${details['creator']}</p>
		        `;
		    }
		});
		
	}
	
	addReviewListeners();	
	
})
.catch(error => console.error("An error occurred:", error));
