# k6 summary

scenario: add_students

- vus: min=1.000, max=1.000
- http_req_connecting: min=0.000, med=0.000, max=0.088, p(90)=0.009, p(95)=0.048, p(99)=0.080, avg=0.009
- http_req_blocked: med=0.011, max=0.120, p(90)=0.026, p(95)=0.073, p(99)=0.110, avg=0.023, min=0.010
- iterations: count=10.000, rate=4.618
- http_req_sending: p(95)=0.145, p(99)=0.177, avg=0.072, min=0.046, med=0.053, max=0.185, p(90)=0.105
- http_req_waiting: min=8.054, med=15.534, max=18.363, p(90)=18.152, p(95)=18.257, p(99)=18.342, avg=15.112
- http_req_duration: max=18.600, p(90)=18.483, p(95)=18.541, p(99)=18.588, avg=15.304, min=8.134, med=15.694
- http_req_tls_handshaking: p(99)=0.000, avg=0.000, min=0.000, med=0.000, max=0.000, p(90)=0.000, p(95)=0.000
- http_req_failed: rate=0.000
- http_req_duration{expected_response:true}: min=8.134, med=15.694, max=18.600, p(90)=18.483, p(95)=18.541, p(99)=18.588, avg=15.304
- http_req_receiving: p(90)=0.160, p(95)=0.176, p(99)=0.189, avg=0.120, min=0.030, med=0.125, max=0.193
