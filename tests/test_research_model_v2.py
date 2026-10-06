import json
from cydra_web2.request_model import RequestTemplate,Parameter,ParameterLocation
from cydra_web2.response_model import summarize
from cydra_web2.artifact import dumps_artifact

def test_single_parameter_mutation_is_bounded():
    r=RequestTemplate("GET","/docs/1",(Parameter("id",ParameterLocation.PATH,"1"),Parameter("role",ParameterLocation.QUERY,"user")))
    x=r.mutate("id","2")
    assert [p.value for p in x.parameters]==["2","user"]

def test_response_semantics_capture_shape_and_redirect():
    x=summarize(200,{"Content-Type":"application/json","Location":"/next"},'{"user":{"id":"1"}}')
    assert "user" in x.json_shape and x.location=="/next"

def test_artifact_is_deterministic_json():
    assert json.loads(dumps_artifact({"b":2,"a":1}))["a"]==1
