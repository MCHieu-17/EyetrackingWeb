# k6 summary

scenario: aoi_summary

- http_req_receiving: avg=0.274, min=0.089, med=0.229, max=1.028, p(90)=0.420, p(95)=0.713, p(99)=0.972
- http_req_waiting: max=231.383, p(90)=213.297, p(95)=218.370, p(99)=231.152, avg=193.862, min=164.547, med=193.578
- vus: min=2.000, max=2.000
- http_req_blocked: med=0.011, max=0.111, p(90)=0.015, p(95)=0.021, p(99)=0.106, avg=0.014, min=0.003
- http_req_duration{expected_response:true}: p(95)=218.938, p(99)=231.376, avg=194.198, min=164.891, med=193.727, max=231.638, p(90)=213.530
- http_req_tls_handshaking: avg=0.000, min=0.000, med=0.000, max=0.000, p(90)=0.000, p(95)=0.000, p(99)=0.000
- iterations: count=52.000, rate=5.061
- http_req_failed: rate=0.000
- http_req_sending: min=0.013, med=0.057, max=0.174, p(90)=0.093, p(95)=0.105, p(99)=0.157, avg=0.061
- http_req_connecting: avg=0.003, min=0.000, med=0.000, max=0.084, p(90)=0.000, p(95)=0.000, p(99)=0.080
- http_req_duration: max=231.638, p(90)=213.530, p(95)=218.938, p(99)=231.376, avg=194.198, min=164.891, med=193.727
