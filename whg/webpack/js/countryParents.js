// countryParents.js

class CountryParents {
    constructor() {
        this.ccodeStorageKey = 'ccode_hash';
        this.regionsStorageKey = 'regions';
        this.dataLoaded = this.init();
    }

    async init() {
        try {
            let ccodeHashData = this.getCachedData(this.ccodeStorageKey);
            let regionsData = this.getCachedData(this.regionsStorageKey);
            if (ccodeHashData && regionsData) {
                console.log('Using cached data:', { ccode_hash: ccodeHashData, regions: regionsData });
                window.ccode_hash = ccodeHashData;
                window.regions = regionsData;
            } else {
                const data = await this.fetchData();
                console.log('Fetched and cached data:', data);
                window.ccode_hash = data.ccode_hash;
                window.regions = data.regions;
            }
        } catch (error) {
            console.error('Error initializing data:', error);
        }
    }

    async fetchData() {
        return new Promise((resolve, reject) => {
            const script = document.createElement('script');
            script.src = '/static/js/parents.js';
            script.onload = () => {
                console.log('After loading parents.js:', {
                    ccode_hash: window.ccode_hash,
                    regions: window.regions
                });
                if (window.ccode_hash && window.regions) {
                    this.cacheData(this.ccodeStorageKey, window.ccode_hash);
                    this.cacheData(this.regionsStorageKey, window.regions);
                    resolve({
                        ccode_hash: window.ccode_hash,
                        regions: window.regions
                    });
                } else {
                    reject(new Error('ccode_hash or regions not found on window object'));
                }
            };
            script.onerror = () => {
                reject(new Error('Error loading script'));
            };
            document.head.appendChild(script);
        });
    }

    cacheData(storageKey, data) {
        localStorage.setItem(storageKey, JSON.stringify(data));
    }

    getCachedData(storageKey) {
        const cachedData = localStorage.getItem(storageKey);
        return cachedData ? JSON.parse(cachedData) : null;
    }
}

export default CountryParents;
