# k6 summary

scenario: outline

- http_req_tls_handshaking: p(90)=0.000, p(95)=0.000, p(99)=0.000, avg=0.000, min=0.000, med=0.000, max=0.000
- http_req_sending: avg=0.038, min=0.003, med=0.039, max=0.143, p(90)=0.052, p(95)=0.066, p(99)=0.088
- http_req_waiting: p(99)=75.797, avg=11.822, min=3.475, med=8.631, max=78.508, p(90)=17.054, p(95)=19.528
- vus: min=5.000, max=5.000
- iterations: count=240.000, rate=23.484
- http_req_duration: p(95)=19.903, p(99)=75.959, avg=12.040, min=3.540, med=8.875, max=78.633, p(90)=17.624
- http_req_duration{expected_response:true}: avg=12.040, min=3.540, med=8.875, max=78.633, p(90)=17.624, p(95)=19.903, p(99)=75.959
- http_req_failed: rate=0.000
- http_req_receiving: avg=0.180, min=0.023, med=0.118, max=0.927, p(90)=0.405, p(95)=0.566, p(99)=0.818
- http_req_blocked: med=0.011, max=0.189, p(90)=0.013, p(95)=0.017, p(99)=0.175, avg=0.014, min=0.001
- http_req_connecting: avg=0.003, min=0.000, med=0.000, max=0.125, p(90)=0.000, p(95)=0.000, p(99)=0.122
