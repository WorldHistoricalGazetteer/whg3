// /whg/webpack/js/carousels.js

import { fetchDataForHorse } from './localGeometryStorage';

export function initialiseCarousels(galleries, carouselMetadata, startCarousels, mappy) {

	var timer;
	const v3 = galleries.length == 1;
	
	galleries.forEach(gallery => {
	    const [title, url] = gallery;
	    const type = v3 ? 'datasets' : title.toLowerCase();
	    const carouselContainer = $(
	        `<div class="carousel-container ${v3 ? 'border mx-0 mx-lg-1 mb-2 mb-lg-0 h-40' : 'p-1'} home-carousel"></div>`);
	    const border = $('<div class="border p-1 h-100 d-flex flex-column"></div>'); // Added flex-column class
	    const heading = $(`<h6 class="p-1 strong">${title}</h6>`);
	    if (type == 'datasets') {
	        heading.addClass('ds-header');
	    } else {
	        heading.addClass('coll-header');
	    }
	    const galleryLink = url == null ?
	        '' :
	        `<span class="float-end small"><a class="linkylite" href="${url}">view all</a></span>`;
	    const carousel = $(
	        `<div id="${type.toLowerCase()}Carousel" class="carousel slide carousel-fade flex-grow-1"></div>`); // Added flex-grow-1 class
	    const carouselInner = $('<div class="carousel-inner"></div>');
	    const prevButton = $(
	        `<button class="carousel-control-prev" type="button" data-bs-target="#${type}Carousel" data-bs-slide="prev">
	                                    <span class="carousel-control-prev-icon" aria-hidden="true"></span>
	                                    <span class="visually-hidden">Previous</span>
	                                </button>`);
	    const nextButton = $(
	        `<button class="carousel-control-next" type="button" data-bs-target="#${type}Carousel" data-bs-slide="next">
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
	    if (v3) {
	        $('#carousel-outer-container').replaceWith(carouselContainer);
	    } else {
	        $('#carousel-outer-container').append(carouselContainer);
	    }
	
	    // Add CSS to ensure full height of carousel items
	    carouselContainer.find('.carousel-inner').css('height', '100%');
	    carouselContainer.find('.carousel-item').css('height', '100%');
	});

    carouselMetadata.forEach(datacollection => {
        const target = $(`#${v3 ? 'dataset' : datacollection.type}sCarousel .carousel-inner`);
        const carouselItem = $(`<div class="carousel-item${target.children(
            '.carousel-item').length == 0 ? ' active' : ''} p-2"></div>`);
        const description = datacollection.description.length > 100 ?
            datacollection.description.substring(0, 100) + '...' :
            datacollection.description;
        if (datacollection.image_file) {
            const imageElement = $(
                `<img src="${datacollection.image_file}" class="carousel-image">`);
            carouselItem.append(imageElement);
        }
        carouselItem.append(`
                    <h6>
                        <a href="${datacollection.url}">${datacollection.title}</a>
                    </h6>
                    <p>${description}</p>
                `).data({
            id: datacollection.ds_or_c_id,
            type: datacollection.type,
            mode: datacollection.display_mode,
            geometry_url: datacollection.geometry_url,
        });
        target.append(carouselItem);
    });

    var carousels = $('.carousel');
    const carouselCount = carousels.length;
    var currentCarousel = 0;
    let delay = 10000;
    let mouseover = false;
    if (startCarousels) carousels.first().carousel({
        interval: delay,
        ride: 'carousel',
        keyboard: false, // Ignore keyboard
    }).on('slide.bs.carousel', function() {
        if (!mouseover) {
            timer = setTimeout(function() {
				currentCarousel += 1;
				currentCarousel = currentCarousel % carouselCount;
                carousels.eq(currentCarousel).carousel('next');
            }, delay / carouselCount);
        }
    });
	// Initialise all remaining carousels
	carousels.slice(1).carousel({
	    keyboard: false, // Ignore keyboard
	});

    carousels.on('slid.bs.carousel', function() {
        $('.carousel-container .border').removeClass('highlight-carousel');
        fetchDataForHorse($(this).find('.carousel-item.active'), mappy);
    });
    $('.carousel-container').on('mouseenter', function() {
        if (startCarousels) carousels.first().carousel('pause');
        clearTimeout(timer);
        mouseover = true;
    }).on('mouseleave', function() {
        if (startCarousels) carousels.first().carousel('cycle');
        mouseover = false;
    });
    // Cycling restarts on button click unless carousel is paused, even though mouse has not left container
    $('.carousel-control-next').on('click', function() {
        if (startCarousels) carousels.first().carousel('pause');
        $($(this).data('bs-target')).carousel('next');
    });
    $('.carousel-control-prev').on('click', function() {
        if (startCarousels) carousels.first().carousel('pause');
        $($(this).data('bs-target')).carousel('prev');
    });
}
