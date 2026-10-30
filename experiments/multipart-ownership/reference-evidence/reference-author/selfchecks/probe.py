import io,json
from werkzeug.formparser import FormDataParser,MultiPartParser,parse_form_data
from werkzeug.datastructures import FileStorage,MultiDict
from werkzeug.wrappers import Request
from werkzeug.exceptions import RequestEntityTooLarge

class Cancel(BaseException):pass
class Sink(io.BytesIO):
 def __init__(self,maximum=None,write_error=None,close_error=None,seek_error=None):
  super().__init__();self.maximum=maximum;self.write_error=write_error;self.close_error=close_error;self.seek_error=seek_error;self.close_calls=0
 def write(self,value):
  if self.write_error is not None:raise self.write_error
  return super().write(bytes(value)[:self.maximum] if self.maximum is not None else value)
 def close(self):
  self.close_calls+=1
  if self.close_error is not None:raise self.close_error
  return super().close()
 def seek(self,*args):
  if self.seek_error is not None:raise self.seek_error
  return super().seek(*args)

B=b'ownership'
def body(parts,close=True):
 value=b''
 for name,filename,data in parts:
  value+=b'--'+B+b'\r\nContent-Disposition: form-data; name="'+name.encode()+b'"'
  if filename is not None:value+=b'; filename="'+filename.encode()+b'"'
  value+=b'\r\n\r\n'+data+b'\r\n'
 return value+(b'--'+B+b'--\r\n' if close else b'')

def parse(parts,**kwargs):
 data=body(parts)
 return MultiPartParser(**kwargs).parse(io.BytesIO(data),B,len(data))
checks=[]
def check(name,fn):
 fn();checks.append(name)

def short():
 sinks=[]
 def factory(**kw):s=Sink(maximum=2);sinks.append(s);return s
 fields,files=parse([('u','x',b'abcdefgh'),('u','y',b'xy'),('t',None,'é'.encode())],stream_factory=factory,max_file_size=8,max_form_data_size=12)
 assert [v.read() for _,v in files.items(multi=True)]==[b'abcdefgh',b'xy']
 assert all(not s.closed for s in sinks)
 assert fields['t']=='é'
 for s in sinks:s.close()
check('inclusive raw-byte aggregate and partial writes',short)

def quota():
 sinks=[]
 def factory(**kw):s=Sink();sinks.append(s);return s
 try:parse([('u','a',b'ab'),('u','b',b'cdef')],stream_factory=factory,max_file_size=3,max_form_data_size=100)
 except RequestEntityTooLarge:pass
 else:raise AssertionError('quota accepted')
 assert len(sinks)==2 and all(s.closed and s.close_calls==1 for s in sinks)
check('quota rolls back completed and active sinks',quota)

def cancel():
 sinks=[];failure=Cancel('cancel')
 def factory(**kw):
  s=Sink(write_error=failure if sinks else None,close_error=RuntimeError('close') if not sinks else None);sinks.append(s);return s
 try:parse([('u','a',b'ab'),('u','b',b'cd')],stream_factory=factory)
 except BaseException as error:assert error is failure
 else:raise AssertionError('cancel accepted')
 assert len(sinks)==2 and all(s.close_calls==1 for s in sinks) and sinks[1].closed
 sinks[0].close_error=None;sinks[0].close()
check('BaseException identity survives cleanup errors',cancel)

def shared():
 sink=Sink()
 req=Request({'wsgi.input':io.BytesIO(), 'REQUEST_METHOD':'POST'})
 req.__dict__['files']=MultiDict([('u',FileStorage(sink)),('u',FileStorage(sink)),('u',FileStorage(Sink()))])
 req.close();assert sink.close_calls==1
 assert all(f.stream.closed for _,f in req.files.items(multi=True))
check('Request duplicate files and shared identity',shared)

def invalid():
 for cls in [MultiPartParser,FormDataParser]:
  for value in [-1,False,1.5,'2']:
   for name in ['max_file_size','max_form_data_size']:
    try:cls(**{name:value})
    except ValueError:pass
    else:raise AssertionError((cls,value,name))
check('invalid quota settings',invalid)
print(json.dumps({'passed':len(checks),'checks':checks}))
