# k6 summary

scenario: replay

- vus: min=2.000, max=2.000
- http_req_duration: min=3.298, med=7.608, max=21.363, p(90)=13.740, p(95)=14.856, p(99)=21.121, avg=9.017
- http_req_waiting: med=7.421, max=21.187, p(90)=13.460, p(95)=14.505, p(99)=20.986, avg=8.807, min=3.170
- http_req_tls_handshaking: p(99)=0.000, avg=0.000, min=0.000, med=0.000, max=0.000, p(90)=0.000, p(95)=0.000
- iterations: count=96.000, rate=9.522
- http_req_blocked: p(90)=0.014, p(95)=0.016, p(99)=0.108, avg=0.014, min=0.003, med=0.011, max=0.113
- http_req_sending: min=0.008, med=0.042, max=0.304, p(90)=0.053, p(95)=0.066, p(99)=0.172, avg=0.045
- http_req_connecting: p(90)=0.000, p(95)=0.000, p(99)=0.072, avg=0.002, min=0.000, med=0.000, max=0.074
- http_req_duration{expected_response:true}: max=21.363, p(90)=13.740, p(95)=14.856, p(99)=21.121, avg=9.017, min=3.298, med=7.608
- http_req_failed: rate=0.000
- http_req_receiving: min=0.023, med=0.133, max=0.434, p(90)=0.338, p(95)=0.364, p(99)=0.433, avg=0.165
