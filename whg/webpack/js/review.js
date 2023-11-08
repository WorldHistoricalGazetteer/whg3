// /whg/webpack/js/review.js

import { mappy, initialiseMap, addReviewListeners } from './review-common';
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

Promise.all([waitMapLoad(), waitDocumentReady()])
    .then(() => {

		console.log(`already: ${ already }`)
		if (already !=='') {
			alert('last record was saved by someone else, this is the next')
		}
	
		$(".view-comments").click(function() {
			$("#record_notes").toggle(300)
		})
		
		addReviewListeners();	
		
    })
    .catch(error => console.error("An error occurred:", error));
