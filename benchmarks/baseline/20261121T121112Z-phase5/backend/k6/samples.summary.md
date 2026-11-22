# k6 summary

scenario: samples

- http_req_duration: min=7.096, med=24.800, max=67.319, p(90)=37.374, p(95)=40.182, p(99)=54.944, avg=25.229
- vus: min=5.000, max=5.000
- http_req_blocked: p(95)=0.017, p(99)=0.131, avg=0.014, min=0.002, med=0.011, max=0.143, p(90)=0.014
- http_req_failed: rate=0.000
- iterations: count=223.000, rate=21.970
- http_req_connecting: med=0.000, max=0.099, p(90)=0.000, p(95)=0.000, p(99)=0.099, avg=0.002, min=0.000
- http_req_sending: avg=0.038, min=0.007, med=0.040, max=0.153, p(90)=0.052, p(95)=0.056, p(99)=0.079
- http_req_tls_handshaking: p(90)=0.000, p(95)=0.000, p(99)=0.000, avg=0.000, min=0.000, med=0.000, max=0.000
- http_req_receiving: avg=0.172, min=0.038, med=0.140, max=0.927, p(90)=0.342, p(95)=0.385, p(99)=0.461
- http_req_duration{expected_response:true}: avg=25.229, min=7.096, med=24.800, max=67.319, p(90)=37.374, p(95)=40.182, p(99)=54.944
- http_req_waiting: p(90)=37.175, p(95)=40.060, p(99)=54.797, avg=25.019, min=6.996, med=24.705, max=67.165
