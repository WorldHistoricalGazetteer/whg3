// base.js

import 'bootstrap/dist/js/bootstrap.bundle.min.js';
import 'jquery-ui/ui/widgets/dialog';
import 'spin/dist/spin.js'; // Instatiates window.Spinner
import ClipboardJS from 'clipboard';

import '../css/base.css';
import 'bootstrap/dist/css/bootstrap.min.css';
import '@fortawesome/fontawesome-free/css/all.min.css';
import 'jquery-ui/themes/base/all.css'; // Include the CSS file
import '../../static/css/styles.css';


if ('fonts' in document) {
	const fontFamilies = ['Raleway'];

	const fontPromises = fontFamilies.flatMap(font => [
		document.fonts.load(`1em "Raleway Regular"`),
		document.fonts.load(`600 1em "Raleway Bold"`),
		document.fonts.load(`italic 1em "Raleway Italic"`),
		document.fonts.load(`italic 600 1em "Raleway Bold Italic"`)
	]);

	Promise.all(fontPromises).then(_ => {
		document.documentElement.classList.add('fonts-loaded');
	});
}


$(function() {
	url = window.location.pathname
	if (url != '/') {
		$("#links_home").addClass('d-none')
		$("#links_other").removeClass('d-none')
	}
	language = window.navigator.language.substr(0, 2)
	abouts = ['/about/', '/system/', '/licensing/', '/credits/']
	clicked = window.location.pathname

	if ($.inArray(clicked, abouts) > -1) {
		console.log('in abouts')
		$("#aboutDropdown").addClass('navactive')
	} else {
		$("[href='" + clicked + "']").addClass('navactive')
	}
});
$(".feedback").click(function() { // TODO: THIS HAS NO PURPOSE UNTIL PAGE IS FULLY LOADED
	console.log(clicked)
	url = window.location.href = "/contact?from=" + clicked
	window.location.href = url
})
