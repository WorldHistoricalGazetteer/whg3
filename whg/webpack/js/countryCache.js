

export class CountryCacheFeatureCollection {
	constructor() {
		this.countryCache = this.loadFromLocalStorage();
	}

	// loadFromLocalStorage() {
	// 	const storedData = localStorage.getItem('countryCache');
	// 	return storedData ? JSON.parse(storedData) : mappy.nullCollection();
	// }

  loadFromLocalStorage() {
		const storedData = localStorage.getItem('countryCache');
		return storedData ? JSON.parse(storedData) : { type: 'FeatureCollection', features: [] };
	}

	saveToLocalStorage() {
		localStorage.setItem('countryCache', JSON.stringify(this.countryCache));
	}
	
	fetchCountries(countries) {
        const missingCountries = countries.filter(countryCode =>
            !this.countryCache.features.some(feature => feature.properties.ccode === countryCode)
        );

        if (missingCountries.length === 0) {
            return Promise.resolve();
        }

        return fetch(`/api/country-features/?country_codes=${missingCountries.join(',')}`)
            .then(response => response.json())
            .then(data => {
                if (data.features.length > 0) {
                    this.countryCache.features = [...this.countryCache.features, ...data.features];
                    this.saveToLocalStorage();
                }
            });
    }
	
	filter(countries) {
        return this.fetchCountries(countries).then(() => {
            return {
                type: 'FeatureCollection',
                features: this.countryCache.features.filter(feature => {
                    const countryCode = feature.properties.ccode;
                    return countries.includes(countryCode);
                }),
            };
        });
    }
}
