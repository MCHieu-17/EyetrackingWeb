# k6 summary

scenario: outline

- http_req_sending: med=0.040, max=0.133, p(90)=0.051, p(95)=0.065, p(99)=0.091, avg=0.041, min=0.007
- http_req_failed: rate=0.000
- http_req_waiting: med=7.852, max=49.935, p(90)=12.432, p(95)=13.193, p(99)=18.549, avg=8.727, min=1.862
- http_req_duration{expected_response:true}: min=1.916, med=8.008, max=50.055, p(90)=12.858, p(95)=13.449, p(99)=18.719, avg=8.925
- http_req_connecting: p(99)=0.080, avg=0.002, min=0.000, med=0.000, max=0.088, p(90)=0.000, p(95)=0.000
- http_req_duration: max=50.055, p(90)=12.858, p(95)=13.449, p(99)=18.719, avg=8.925, min=1.916, med=8.008
- vus: min=5.000, max=5.000
- http_req_blocked: min=0.003, med=0.011, max=0.118, p(90)=0.014, p(95)=0.018, p(99)=0.101, avg=0.013
- http_req_tls_handshaking: p(95)=0.000, p(99)=0.000, avg=0.000, min=0.000, med=0.000, max=0.000, p(90)=0.000
- http_req_receiving: med=0.127, max=1.457, p(90)=0.331, p(95)=0.431, p(99)=0.694, avg=0.157, min=0.011
- iterations: count=240.000, rate=23.636
