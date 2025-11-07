def get_asia_oceania_cities() -> list[str]:
    """Returns major cities from Asia and Oceania"""
    return [
        "Tokyo", "Delhi", "Shanghai", "Mumbai", "Beijing",
        "Seoul", "Bangkok", "Manila", "Sydney", "Melbourne",
        "Jakarta", "Osaka", "Karachi", "Dhaka", "Hong Kong",
        "Bangalore", "Kolkata", "Chennai", "Hyderabad", "Singapore",
        "Kuala Lumpur", "Ho Chi Minh City", "Hanoi", "Taipei",
        "Guangzhou", "Shenzhen", "Chongqing", "Chengdu", "Wuhan",
        "Xi'an", "Tianjin", "Suzhou", "Nanjing", "Hangzhou",
        "Auckland", "Brisbane", "Perth", "Adelaide", "Yangon",
        "Phnom Penh", "Vientiane", "Kathmandu", "Colombo", "Islamabad",
        "Lahore", "Ahmedabad", "Pune", "Jaipur", "Lucknow",
        "Kanpur", "Nagpur", "Surat", "Busan", "Incheon",
        "Kyoto", "Yokohama", "Sapporo", "Fukuoka", "Kobe"
    ]

def get_europe_africa_middleeast_cities() -> list[str]:
    """Returns major cities from Europe, Africa, and Middle East"""
    return [
        "London", "Paris", "Edinburgh", "Istanbul", "Warsaw",
        "Cairo", "Lagos", "Nairobi", "Tehran", "Dubai", "Kyiv",
        "Berlin", "Madrid", "Rome", "Barcelona", "Amsterdam",
        "Vienna", "Brussels", "Munich", "Hamburg", "Prague",
        "Budapest", "Copenhagen", "Stockholm", "Oslo", "Helsinki",
        "Dublin", "Lisbon", "Athens", "Milan", "Manchester",
        "Birmingham", "Glasgow", "Zurich", "Geneva", "Frankfurt",
        "Cologne", "Stuttgart", "Valencia", "Seville", "Porto",
        "Marseille", "Lyon", "Toulouse", "Nice", "Krakow",
        "Bucharest", "Sofia", "Belgrade", "Zagreb", "Bratislava",
        "Johannesburg", "Cape Town", "Kinshasa", "Luanda", "Dar es Salaam",
        "Khartoum", "Alexandria", "Casablanca", "Algiers", "Addis Ababa",
        "Accra", "Abidjan", "Kano", "Ibadan", "Dakar",
        "Riyadh", "Jeddah", "Baghdad", "Amman", "Beirut",
        "Damascus", "Jerusalem", "Tel Aviv", "Doha", "Kuwait City",
        "Muscat", "Abu Dhabi", "Ankara", "Izmir", "Sanaa"
    ]

def get_americas_cities() -> list[str]:
    """Returns major cities from North and South America"""
    return [
        "New York", "Los Angeles", "Mexico City", "São Paulo", "Toronto",
        "Buenos Aires", "Rio de Janeiro", "Chicago", "Bogotá", "Lima",
        "Houston", "Phoenix", "Philadelphia", "San Antonio", "San Diego",
        "Dallas", "San Jose", "Austin", "Jacksonville", "Fort Worth",
        "Columbus", "Charlotte", "San Francisco", "Indianapolis", "Seattle",
        "Denver", "Washington", "Boston", "Detroit", "Nashville",
        "Portland", "Las Vegas", "Miami", "Atlanta", "Vancouver",
        "Montreal", "Calgary", "Edmonton", "Ottawa", "Winnipeg",
        "Guadalajara", "Monterrey", "Puebla", "Tijuana", "León",
        "Santiago", "Caracas", "Guayaquil", "Quito", "Cali",
        "Medellín", "Cartagena", "Belo Horizonte", "Brasília", "Salvador",
        "Fortaleza", "Curitiba", "Recife", "Porto Alegre", "Manaus",
        "Córdoba", "Rosario", "Mendoza", "La Paz", "Santa Cruz",
        "Montevideo", "Asunción", "San Juan", "Panama City", "San José",
        "Havana", "Santo Domingo", "Port-au-Prince", "Guatemala City", "Tegucigalpa"
    ]

def get_all_cities() -> list[str]:
    """Returns all tracked cities from all regions combined"""
    return (
        get_asia_oceania_cities() +
        get_europe_africa_middleeast_cities() +
        get_americas_cities()
    )
