# Olympus StoredObject Class
# This is a stored object, the base form of an object that can be stored in our database

from abc import ABCMeta, abstractmethod
from Storage import Storage
import random, time, datetime, copy

class StoredObject():
	""" This is a StoredObject, the base class of anything that is to be stored in our database.
	Inheriting from this in lieu of communicating directly with PyMongo or Storage() will allow you to instantaneously save, merge and remove your objects. As this is an abstract class it cannot be instantiated directly and must therefor be subclassed.
	"""
	__metaclass__ = ABCMeta
	
	def __init__(self, database=None, collection=None, name = ""):
		""" Sets up the object
		
		:param database: Optional, the database where this object is to be stored.
		:param collection: Optional, the collecion where this object is to be stored.
		:param name: The pretty name of this object.
		"""
		self._database = database
		self._collection = collection
		self.name = name
		self._created = datetime.datetime.now()
		self._type = self.__class__.__name__
	
	def setDatabase(self,database):
		"""Sets the database for this object."""
		self._database = database
		
	def setCollection(self, collection):
		"""Sets the collection for this object. This is analogous to a table in relational databases."""
		self._collection = collection
	
	def save(self):
		"""Save this object into the database with all its public attributes."""
		# Can't save without a database or a table
		if self._database is None:
			raise ValueError, "No database has been selected."
		if self._collection is None:
			raise ValueError, "No collection has been selected."
	
		# Check private variables. We probably shouldn't store these.
		document = {}	
		for key, value in self.__dict__.items():
			key = key.replace("_"+self._type, "")
			if key.startswith("__"):
				continue
			document[key] = value
		
		# Let's store this object
		storage = Storage()
		storage.getDatabase(self._database)
		storage.getCollection(self._collection)
		storage.insertDocuments(document)
		self._id = document["_id"]
	
	def loadFromRawData(self, data):
		""" This will create an object of the given class from a raw dictionary. Typically this would be what comes out of a the database, but it can also be used to initiate a whole new object from scratch.
		
		:param data: A dictionary containing the data to be set for this new object.
		:rtype: A new instance of this class with all the data specified pre set.
		"""
		newObject = self.__class__
		for key, value in data.items():
			setattr(newObject, key, value)
			
		return newObject
	
	def getObjectsByKey(self, key, value, limit=None):
		""" This will retrieve documents from the database and collection specified by this object based on one of their keys and convert them to their proper Python object state.
		
		:param key: The key to select on.
		:param value: The value to search for.
		:param limit: The maximum amount of objects to return. Will return all results by default.
		:rtype: All the matching objects stored in the database.
		"""
		storage = Storage()
		database = self._database
		collection = self._collection
		
		if database is None or collection is None:
			raise ValueError, "The object needs to be assigned a database and a collection."
		
		storage.getDatabase(database)
		storage.getCollection(collection)
		documents = storage.getDocuments({key:value}, limit)
		
		objects = [ self.loadFromRawData( data ) for data in documents ]
		return objects
		
	def remove(self):
		""" Removes this object from the database. It will still remain in memory, however, and can be resaved at a later time provided that the original reference is maintained."""
		storage = Storage()
		database = self._database
		collection = self._collection
		
		if database is None or collection is None:
			raise ValueError, "The object needs to be assigned a database and a collection."
		
		storage.getDatabase(database)
		storage.getCollection(collection)
		documents = storage.removeDocuments({"_id":self._id})
		
	def setAttribute(self, attr, source, value):
		""" Set the given attribute to this value. It will overwrite any previous data.
		
		:param attr: The name of the attribute.
		:param source: The source of data to be set.
		:param value: The value that should be set for this source.
		"""
		attribute = {}
		attribute[source] = value
		setattr(self,attr,attribute)
		
	def addAttribute(self, attr, source, value):
		""" Add the given attribute to this value. It will retain any other data from other sources, but will overwrite any data from the same source in this attribute.
		
		:param attr: The name of the attribute.
		:param source: The source of data to be set.
		:param value: The value that should be set for this source.
		"""
		attribute = getattr(self, attr, {})
		attribute[source] = value
		setattr(self,attr,attribute)

	def getAttribute(self, attr, source):
		""" Will return the data stored in this attribute from the given source.
		
		:param attr: The name of the attribute.
		:param source: The source of data to be set.
		:rtype: The data stored in this attribute from this source.
		"""
		if not hasattr(self, attr):
			return None			
		attribute = getattr(self, attr, {})
		return attribute.get(source, None)
		
	def __add__(self, other):
		""" Overloads the + (plus) operator and uses it to merge two objects. If there is a conflict for a key the value from the first object in the equation will be chosen.
		
		For example::
			
		    ProteinOne = Protein()
		    ProteinTwo = Protein()
		    ProteinOne.setAttribute("attribute", "source", "ValueOne")
		    ProteinOne.setAttribute("attribute", "source", "ValueTwo")
			
		    ProteinMerged = ProteinOne + ProteinTwo
		    ProteinMerged.getAttribute("attribute","source") == "ValueOne" # Yields True
		
		The original two objects will not be affected.
		
		:param other: The object that this object will be merged with.
		:rtype: A new object with the merged date from the two given objects.
		"""
		attributes = self.mergeObjects(self,other)
		newObject = self.__class__()
		newObject.__dict__ = attributes
		return newObject
		
	def mergeObjects(self, objectOne, objectTwo, path=None):
		""" Takes the attributes from two objects and attempts to merge them. If there is a conflict for a key the value from the first object in will be chosen.
		
		:param objectOne: The first object
		:param objectTwo: The second object
		:param path: The root of the merger.
		:rtype: A dictionary of merged values.
		"""
		a = copy.deepcopy(objectOne.__dict__)
		b = copy.deepcopy(objectTwo.__dict__)
		
		attributes = self.merge(a,b,path)
		return attributes
		
	def merge(self, a, b, path=None):
		""" Recursively merges two dictionaries. If there is a conflict for a key the value from the first object in will be chosen. All the changes are inserted into the first dictionary.
		
		:param a: The first dictionary.
		:param b: The second dictionary.
		:param path: The root of the merger.
		:rtype: A dictionary of merged values.
		"""
		if path is None: path = []
		for key in b:
			if key in a:
				if isinstance(a[key], dict) and isinstance(b[key], dict):
					self.merge(a[key], b[key], path + [str(key)])
				elif a[key] == b[key]:
					pass # same leaf value
				else:
					# Conflict, use the value from A
					pass
					
			else:
				a[key] = b[key]
		return a
		
		
# For testing purposes only #
		
class TestObject(StoredObject):
	""" TestObject implements only the most basic of the StorageObject's methods for testing purposes. """
	def __init__(self):
		super(TestObject, self).__init__(database = "test_database", collection = "test_collection")

import random
r = random.randrange(1000000000,9999999999)
		
def test_setAttribute():
	t = TestObject()
	t.setAttribute("random", "python", r)
	assert t.random["python"] == r
	
def test_addAttribute():
	t = TestObject()
	t.addAttribute("random", "python", r)
	t.addAttribute("random", "lua", r+1)
	assert t.random["python"] == r
	assert t.random["lua"] == r+1
	
def test_getAttribute():
	t = TestObject()
	t.addAttribute("random", "python", r)
	assert t.getAttribute("random", "python") == r
		
def test_createTestObject():
	t = TestObject()
	t.random = r
	t.save()

def test_findTestObject():
	t = TestObject().getObjectsByKey("random",r)
	assert len(t) > 0
	assert t[0].random == r
	
def test_removeObject():
	t = TestObject().getObjectsByKey("random",r)
	t[0]().remove()
	
def test_loadFromRawData():
	t = TestObject().loadFromRawData({"r":r})
	assert t.r == r
	
def test_mergeObjects():
	t1 = TestObject()
	t2 = TestObject()
	
	t1.addAttribute("rand", "python", r)
	t2.addAttribute("rand", "lua", r+1)
	resultingAttributes = TestObject().mergeObjects(t1,t2)
	
	assert resultingAttributes["rand"]["python"] == r
	assert resultingAttributes["rand"]["lua"] == r+1
	
def test_mergeByAddOperator():
	t1 = TestObject()
	t2 = TestObject()
	t1.addAttribute("rand", "python", r)
	t2.addAttribute("rand", "lua", r+1)
	
	t3 = t1+t2
	assert t3.getAttribute("rand", "python") == r
	assert t3.getAttribute("rand", "lua") == r+1
	