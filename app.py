import os
import json
# import folium
import requests
import matplotlib.pyplot as plt
from pymongo import MongoClient
from flask import Flask, render_template,abort,request
import threading


api_key = "03def23f4f250867fa0abb2f5c7ab004"
extreme_conditions = ["Rain","snow"]
forecast_url = "http://api.openweathermap.org/data/2.5/forecast?q={city_name}&appid={api_key}"
weather_url = "http://api.openweathermap.org/data/2.5/weather?q={city_name}&appid={api_key}"

try:  
    my_mongo_client = MongoClient() 
    print("Connected successfully!!!")
    print("DB List: ",my_mongo_client.list_database_names())
except:   
    print("Could not connect to MongoDB") 

opneWeather_db = my_mongo_client["openWeather"] 
print("Collection Names: ",opneWeather_db.list_collection_names())
weather_collection = opneWeather_db["weather_forecast"]
print("Collection Names: ",opneWeather_db.list_collection_names())


def fetch_forecast_data_for_a_city(city_name):
    final_url = forecast_url.format(city_name=city_name,api_key=api_key)    
    response = requests.get(final_url)
    
    if response.status_code == 200:
        response = response.json()        
        mongo_format = {'city_name': response["city"]["name"]
                        ,'country': response["city"]["country"]
                        ,'forecast_values': response["list"]
                        ,'coordinates':str(response["city"]["coord"]["lat"])+","+str(response["city"]["coord"]["lon"])}
        record_id = weather_collection.insert_one(mongo_format) 

        # print("city: ", city, "inserted_ids: ", record_id.inserted_id)
        get_record_query = { "_id":record_id.inserted_id}
        results_cursor = weather_collection.find(get_record_query)
        
        temperature_readings, dates_readings =[], []
        freeze_readings = []
        extreme_readings = []
        
        
        for a_record in results_cursor:    
            for a_forecast in a_record['forecast_values']: 
                temperature = a_forecast['main']['temp']
                temperature_farenheit = 1.8 * (temperature - 273) + 32
                temperature_readings.append(temperature_farenheit)
                dates_readings.append(a_forecast['dt_txt'])
                if temperature_farenheit < 2: freeze_readings.append('[ALERT]: {}'.format(a_forecast['dt_txt']))
                if a_forecast['weather'][0]['main'] in extreme_conditions: extreme_readings.append("{} on {}".format(a_forecast['weather'][0]['main'],a_forecast['dt_txt']))
                    
        plt.plot(dates_readings,temperature_readings)
        plt.title("Forecast of Temperatures in {}".format(city_name))
        plt.xlabel("Date and time")
        plt.ylabel("Temperature(F)")
        plt.xticks(dates_readings, dates_readings, rotation=90)
        plt.tick_params(axis='x', which='major', labelsize=5)        
        plt.savefig("static/myfolder/"+city_name+"_plot.png")
        # plt.show()
        plt.close()
        
    return [freeze_readings,extreme_readings]

def fetch_current_data_for_a_city(city_name):
    
    final_url = weather_url.format(city_name=city_name,api_key=api_key)    
    response = requests.get(final_url)
    
    if response.status_code == 200:
        response = response.json()        
        return response
    else:
        return {}

    
def get_map_for_city(city_name):
    layers = ["temp_new","wind_new","pressure_new","precipitation_new","clouds_new"]
    maps_format = "https://tile.openweathermap.org/map/{layer}/{z}/{x}/{y}.png?q={city_name}&appid={API_key}"
    maps_url = maps_format.format(layer=layers[2],z=1,x=1,y=1,API_key=api_key,city_name=city_name)
    
    response = requests.get(maps_url)
    
    map_path = "static/myfolder/"+city_name+".png"

    if response.status_code == 200:
        with open(map_path, 'wb') as file:
            file.write(response.content)
        print(response.status_code)
        return map_path
    
app = Flask(__name__)
PEOPLE_FOLDER = os.path.join('static', 'myfolder')
app.config['UPLOAD_FOLDER'] = PEOPLE_FOLDER


@app.route('/',methods=['POST','GET'])
def index():
    
    if request.method == 'POST':
        city = request.form['city']
    else:
        #for default name mathura
        city = 'london'

    # source contain json data from api
    try:
        forecast_response = fetch_forecast_data_for_a_city(city)
        current_response = fetch_current_data_for_a_city(city)
        map_path = get_map_for_city(city)
        t1 = threading.Thread(target=fetch_forecast_data_for_a_city,args=city)
        t2 = threading.Thread(target=fetch_current_data_for_a_city,args=city)
        t3 = threading.Thread(target=get_map_for_city,args=city)

        t1.start()
        t2.start()
        t3.start()

        t1.join()
        t2.join()
        t3.join()
        freeze_alert ="Freezing temperature on" + "\n ".join(forecast_response[0])
        extreme_alert = "Forecast is observed to be"+"\n ".join(forecast_response[1])
        freeze_alert =forecast_response[0]
        extreme_alert = forecast_response[1]
    except Exception as ex:
        print("ex: ",ex)
        return abort(404)
    
    data = {
        "cityname":city,
        "country_code": current_response['sys']['country'],
        "coordinate": str(current_response['coord']['lat']) +", "+str(current_response['coord']['lon']),
        "temp_cel": 1.8 * (current_response['main']['temp'] - 273) + 32,
        "pressure": current_response['main']['pressure'],
        "humidity": current_response['main']['humidity'],
    }
    
    full_filename = os.path.join(app.config['UPLOAD_FOLDER'],city+"_plot.png")
    
    return render_template('index.html',city=city.capitalize(),data=data,image_path=full_filename,image_name=city.capitalize(),freeze_alert=freeze_alert,extreme_alert=extreme_alert,map_path=map_path)

if __name__ == '__main__':

    app.run(debug=True)