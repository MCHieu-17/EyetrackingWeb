# k6 summary

scenario: replay

- http_req_tls_handshaking: p(99)=0.000, avg=0.000, min=0.000, med=0.000, max=0.000, p(90)=0.000, p(95)=0.000
- iterations: count=84.000, rate=8.314
- http_req_connecting: med=0.000, max=0.084, p(90)=0.000, p(95)=0.000, p(99)=0.083, avg=0.002, min=0.000
- http_req_duration: avg=39.677, min=17.125, med=39.365, max=80.312, p(90)=53.368, p(95)=56.421, p(99)=76.217
- http_req_duration{expected_response:true}: max=80.312, p(90)=53.368, p(95)=56.421, p(99)=76.217, avg=39.677, min=17.125, med=39.365
- http_req_blocked: p(95)=0.019, p(99)=0.114, avg=0.014, min=0.002, med=0.011, max=0.115, p(90)=0.015
- http_req_receiving: min=0.040, med=0.095, max=0.415, p(90)=0.165, p(95)=0.206, p(99)=0.332, avg=0.110
- http_req_sending: min=0.007, med=0.041, max=0.076, p(90)=0.051, p(95)=0.056, p(99)=0.075, avg=0.039
- vus: min=2.000, max=2.000
- http_req_waiting: p(95)=56.292, p(99)=76.074, avg=39.528, min=17.028, med=39.207, max=80.174, p(90)=53.201
- http_req_failed: rate=0.000
