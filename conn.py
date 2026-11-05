from pymongo import MongoClient
#URL de MongoDB
client = MongoClient("mongodb+srv://grearte:xS8fu8gVPAz9qGWm@cluster0.dffoict.mongodb.net/?retryWrites=true&w=majority")
#Seleccionar la db
# db = client['Estudiantes']
#Seleccionar la colección
# collection_turistas = db['turista']
# collection_lugares = db['lugar']