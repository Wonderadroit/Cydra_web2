from cydra_web2.differential import DifferentialPlanner
from cydra_web2.model import Identity,Resource,Endpoint,TargetModel

def test_plan_ownership_only_uses_authenticated_identities_and_materialized_resources():
 m=TargetModel("https://authorized.example"); m.add_identity(Identity("anon","anon",False)); m.add_identity(Identity("alice","user",True)); m.add_resource(Resource("r1","profile",None,"123")); m.add_endpoint(Endpoint("GET /profiles/{id}","GET","/profiles/{id}",("r1",)))
 xs=DifferentialPlanner().plan_ownership(m)
 assert [(x.identity_id,x.path) for x in xs]==[("alice","/profiles/123")]

def test_plan_ownership_fails_closed_without_identifier():
 m=TargetModel("https://authorized.example"); m.add_identity(Identity("alice","user",True)); m.add_resource(Resource("r1","profile",None,None)); m.add_endpoint(Endpoint("GET /profiles/{id}","GET","/profiles/{id}",("r1",)))
 assert DifferentialPlanner().plan_ownership(m)==()
